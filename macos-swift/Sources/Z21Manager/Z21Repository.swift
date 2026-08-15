import Foundation

final class Z21Repository {
    private let database: SQLiteDatabase
    private let tables: Set<String>

    init(databaseURL: URL) throws {
        database = try SQLiteDatabase(url: databaseURL)
        tables = try database.tables()
        guard tables.contains("vehicles") else {
            throw Z21Error.database("SQLite database has no vehicles table.")
        }
    }

    func loadLocomotives() throws -> [Locomotive] {
        let columns = try database.columns(in: "vehicles")
        let wanted = [
            "id", "name", "address", "max_speed", "active", "traction_direction",
            "image_name", "drivers_cab", "description", "full_name", "railway",
            "article_number", "decoder_type", "build_year", "buffer_lenght",
            "model_buffer_lenght", "service_weight", "model_weight", "rmin", "ip",
            "speed_display", "type", "crane", "in_stock_since", "inStockSince",
            "in_stock_since_date"
        ].filter(columns.contains)
        let order = columns.contains("position") ? "position" : "id"
        let rows = try database.rows(
            "SELECT \(wanted.map(quoteIdentifier).joined(separator: ", ")) FROM vehicles WHERE type IN (0, 1, 2) ORDER BY \(quoteIdentifier(order))"
        )
        return try rows.map { row in
            var locomotive = Locomotive()
            locomotive.vehicleID = row.int("id")
            locomotive.name = row.text("name")
            locomotive.address = row.integer("address")
            locomotive.speed = row.integer("max_speed")
            locomotive.active = row.bool("active", default: true)
            locomotive.direction = row.integer("traction_direction") == 1
            locomotive.imageName = row.text("image_name")
            locomotive.driversCab = row.text("drivers_cab")
            locomotive.description = row.text("description")
            locomotive.fullName = row.text("full_name")
            locomotive.railway = row.text("railway")
            locomotive.articleNumber = row.text("article_number")
            locomotive.decoderType = row.text("decoder_type")
            locomotive.buildYear = row.text("build_year")
            locomotive.bufferLength = row.text("buffer_lenght")
            locomotive.modelBufferLength = row.text("model_buffer_lenght")
            locomotive.serviceWeight = row.text("service_weight")
            locomotive.modelWeight = row.text("model_weight")
            locomotive.rmin = row.text("rmin")
            locomotive.ip = row.text("ip")
            locomotive.speedDisplay = row.integer("speed_display")
            locomotive.railVehicleType = row.integer("type")
            locomotive.crane = row.bool("crane")
            locomotive.inStockSince = row.text("in_stock_since", fallback: row.text("inStockSince", fallback: row.text("in_stock_since_date")))
            if let id = locomotive.vehicleID {
                locomotive.categories = try loadCategories(vehicleID: id)
                locomotive.regulationStep = try loadRegulationStep(vehicleID: id)
                locomotive.functions = try loadFunctions(vehicleID: id)
            }
            return locomotive
        }
    }

    func save(_ locomotives: inout [Locomotive]) throws {
        try database.transaction {
            let vehicleColumns = try database.columns(in: "vehicles")
            var kept = Set<Int64>()
            for index in locomotives.indices {
                let id: Int64
                if let stored = locomotives[index].vehicleID,
                   try database.scalarInt("SELECT id FROM vehicles WHERE id = ?", [.integer(stored)]) != nil {
                    id = stored
                    try updateVehicle(locomotives[index], id: id, columns: vehicleColumns)
                } else {
                    id = try insertVehicle(locomotives[index], columns: vehicleColumns)
                    locomotives[index].vehicleID = id
                    locomotives[index].isNewImport = false
                }
                kept.insert(id)
                try syncFunctions(locomotives[index].functions, vehicleID: id)
                try syncCategories(locomotives[index].categories, vehicleID: id)
                try syncTraction(locomotives[index].regulationStep, vehicleID: id)
            }
            let existing = try database.rows("SELECT id FROM vehicles WHERE type IN (0, 1, 2)").compactMap { $0["id"]?.int }
            for id in existing where !kept.contains(id) { try deleteLocomotive(id: id) }
        }
    }

    private func loadFunctions(vehicleID: Int64) throws -> [FunctionInfo] {
        guard tables.contains("functions") else { return [] }
        let columns = try database.columns(in: "functions")
        let wanted = ["function", "position", "shortcut", "time", "image_name", "button_type", "is_configured"].filter(columns.contains)
        let order = columns.contains("position") ? "position" : "function"
        return try database.rows(
            "SELECT \(wanted.map(quoteIdentifier).joined(separator: ", ")) FROM functions WHERE vehicle_id = ? ORDER BY \(quoteIdentifier(order))",
            [.integer(vehicleID)]
        ).map { row in
            FunctionInfo(number: row.integer("function"), imageName: row.text("image_name"),
                         shortcut: row.text("shortcut"), position: row.integer("position"),
                         time: row["time"]?.double, buttonType: row.integer("button_type"),
                         isActive: row.bool("is_configured", default: true))
        }
    }

    private func loadCategories(vehicleID: Int64) throws -> [String] {
        guard tables.isSuperset(of: ["categories", "vehicles_to_categories"]) else { return [] }
        let links = try database.columns(in: "vehicles_to_categories")
        let order = links.contains("id") ? "vtc.id" : "c.name"
        return try database.rows("""
            SELECT c.name FROM categories c
            INNER JOIN vehicles_to_categories vtc ON c.id = vtc.category_id
            WHERE vtc.vehicle_id = ? ORDER BY \(order)
            """, [.integer(vehicleID)]).compactMap { $0["name"]?.string }
    }

    private func loadRegulationStep(vehicleID: Int64) throws -> Int {
        guard tables.contains("traction_list") else { return 0 }
        return Int(try database.scalarInt(
            "SELECT regulation_step FROM traction_list WHERE loco_id = ? ORDER BY regulation_step LIMIT 1",
            [.integer(vehicleID)]) ?? 0)
    }

    private func vehicleValues(_ locomotive: Locomotive, columns: Set<String>, position: Int? = nil) -> [String: SQLiteValue] {
        var values: [String: SQLiteValue] = [
            "type": .integer(Int64(locomotive.railVehicleType)), "name": .text(locomotive.name),
            "address": .integer(Int64(locomotive.address)), "max_speed": .integer(Int64(locomotive.speed)),
            "active": .integer(locomotive.active ? 1 : 0), "traction_direction": .integer(locomotive.direction ? 1 : 0),
            "image_name": nullable(locomotive.imageName), "drivers_cab": nullable(locomotive.driversCab),
            "description": nullable(locomotive.description), "full_name": nullable(locomotive.fullName),
            "railway": nullable(locomotive.railway), "article_number": nullable(locomotive.articleNumber),
            "decoder_type": nullable(locomotive.decoderType), "build_year": nullable(locomotive.buildYear),
            "buffer_lenght": nullable(locomotive.bufferLength), "model_buffer_lenght": nullable(locomotive.modelBufferLength),
            "service_weight": nullable(locomotive.serviceWeight), "model_weight": nullable(locomotive.modelWeight),
            "rmin": nullable(locomotive.rmin), "ip": nullable(locomotive.ip),
            "speed_display": .integer(Int64(locomotive.speedDisplay)), "crane": .integer(locomotive.crane ? 1 : 0)
        ]
        if let position { values["position"] = .integer(Int64(position)) }
        if let stock = ["in_stock_since", "inStockSince", "in_stock_since_date"].first(where: columns.contains) {
            values[stock] = nullable(locomotive.inStockSince)
        }
        return values.filter { columns.contains($0.key) }
    }

    private func updateVehicle(_ locomotive: Locomotive, id: Int64, columns: Set<String>) throws {
        let values = vehicleValues(locomotive, columns: columns).sorted { $0.key < $1.key }
        try database.execute(
            "UPDATE vehicles SET \(values.map { "\(quoteIdentifier($0.key)) = ?" }.joined(separator: ", ")) WHERE id = ?",
            values.map(\.value) + [.integer(id)])
    }

    private func insertVehicle(_ locomotive: Locomotive, columns: Set<String>) throws -> Int64 {
        let maxPosition = try database.scalarInt(
            "SELECT MAX(position) FROM vehicles WHERE type = ?",
            [.integer(Int64(locomotive.railVehicleType))]
        ) ?? 0
        let values = vehicleValues(locomotive, columns: columns, position: Int(maxPosition + 1)).sorted { $0.key < $1.key }
        try database.execute(
            "INSERT INTO vehicles (\(values.map { quoteIdentifier($0.key) }.joined(separator: ", "))) VALUES (\(values.map { _ in "?" }.joined(separator: ", ")))",
            values.map(\.value))
        return database.lastInsertID
    }

    private func syncFunctions(_ functions: [FunctionInfo], vehicleID: Int64) throws {
        guard tables.contains("functions") else { return }
        let existing = Set(try database.rows("SELECT function FROM functions WHERE vehicle_id = ?", [.integer(vehicleID)]).compactMap { $0["function"]?.int }.map(Int.init))
        let current = Set(functions.map(\.number))
        for number in existing.subtracting(current) {
            try database.execute("DELETE FROM functions WHERE vehicle_id = ? AND function = ?", [.integer(vehicleID), .integer(Int64(number))])
        }
        for (position, function) in functions.sorted(by: { ($0.position, $0.number) < ($1.position, $1.number) }).enumerated() {
            let commonValues: [SQLiteValue] = [
                .integer(Int64(position)), .text(function.shortcut), function.time.map(SQLiteValue.double) ?? .null,
                .text(function.imageName), .integer(Int64(function.buttonType))
            ]
            if existing.contains(function.number) {
                try database.execute("""
                    UPDATE functions SET position=?, shortcut=?, time=?, image_name=?, button_type=?, is_configured=?, show_function_number=1
                    WHERE vehicle_id=? AND function=?
                    """, commonValues + [
                        .integer(function.isActive ? 1 : 0), .integer(vehicleID), .integer(Int64(function.number))
                    ])
            } else {
                try database.execute("""
                    INSERT INTO functions (position, shortcut, time, image_name, button_type, vehicle_id, function, is_configured, show_function_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, commonValues + [
                        .integer(vehicleID), .integer(Int64(function.number)), .integer(function.isActive ? 1 : 0)
                    ])
            }
        }
    }

    private func syncCategories(_ names: [String], vehicleID: Int64) throws {
        guard tables.isSuperset(of: ["categories", "vehicles_to_categories"]) else { return }
        var ids: [Int64] = []
        var seen = Set<String>()
        for name in names.map({ $0.trimmingCharacters(in: .whitespacesAndNewlines) }) where !name.isEmpty {
            guard seen.insert(name.lowercased()).inserted else { continue }
            if let id = try database.scalarInt("SELECT id FROM categories WHERE name = ? COLLATE NOCASE", [.text(name)]) {
                ids.append(id)
            } else {
                try database.execute("INSERT INTO categories (name) VALUES (?)", [.text(name)])
                ids.append(database.lastInsertID)
            }
        }
        try database.execute("DELETE FROM vehicles_to_categories WHERE vehicle_id = ?", [.integer(vehicleID)])
        for id in ids {
            try database.execute("INSERT INTO vehicles_to_categories (vehicle_id, category_id) VALUES (?, ?)", [.integer(vehicleID), .integer(id)])
        }
    }

    private func syncTraction(_ step: Int, vehicleID: Int64) throws {
        guard tables.contains("traction_list") else { return }
        if step == 0 {
            try database.execute("DELETE FROM traction_list WHERE loco_id = ?", [.integer(vehicleID)])
            return
        }
        try database.execute("UPDATE traction_list SET regulation_step = ? WHERE loco_id = ?", [.integer(Int64(step)), .integer(vehicleID)])
        if sqliteChanges() == 0 {
            try database.execute("INSERT INTO traction_list (loco_id, regulation_step, time) VALUES (?, ?, 0.0)", [.integer(vehicleID), .integer(Int64(step))])
        }
    }

    private func sqliteChanges() -> Int { Int(try! database.scalarInt("SELECT changes()") ?? 0) }

    private func deleteLocomotive(id: Int64) throws {
        if tables.contains("functions") { try database.execute("DELETE FROM functions WHERE vehicle_id = ?", [.integer(id)]) }
        if tables.contains("vehicles_to_categories") { try database.execute("DELETE FROM vehicles_to_categories WHERE vehicle_id = ?", [.integer(id)]) }
        if tables.contains("traction_list") { try database.execute("DELETE FROM traction_list WHERE loco_id = ?", [.integer(id)]) }
        try database.execute("DELETE FROM vehicles WHERE id = ?", [.integer(id)])
    }
}

private func nullable(_ value: String) -> SQLiteValue { value.isEmpty ? .null : .text(value) }

private extension Dictionary where Key == String, Value == SQLiteValue {
    func text(_ key: String, fallback: String = "") -> String { self[key]?.string ?? fallback }
    func integer(_ key: String) -> Int { Int(self[key]?.int ?? 0) }
    func int(_ key: String) -> Int64? { self[key]?.int }
    func bool(_ key: String, default fallback: Bool = false) -> Bool {
        guard let value = self[key]?.int else { return fallback }
        return value != 0
    }
}
