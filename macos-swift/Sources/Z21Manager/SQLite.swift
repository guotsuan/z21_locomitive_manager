import Foundation
import CSQLite

enum SQLiteValue {
    case integer(Int64), double(Double), text(String), null
}

final class SQLiteDatabase {
    private var handle: OpaquePointer?

    init(url: URL, readOnly: Bool = false) throws {
        let flags = readOnly ? SQLITE_OPEN_READONLY : (SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE)
        guard sqlite3_open_v2(url.path, &handle, flags, nil) == SQLITE_OK else {
            let message = handle.map { String(cString: sqlite3_errmsg($0)) } ?? "Unable to open SQLite database"
            if let handle { sqlite3_close(handle) }
            throw Z21Error.database(message)
        }
        sqlite3_busy_timeout(handle, 5_000)
        try execute("PRAGMA foreign_keys = OFF")
    }

    deinit { sqlite3_close(handle) }

    func execute(_ sql: String, _ values: [SQLiteValue] = []) throws {
        let statement = try prepare(sql)
        defer { sqlite3_finalize(statement) }
        try bind(values, to: statement)
        guard sqlite3_step(statement) == SQLITE_DONE else { throw lastError() }
    }

    func rows(_ sql: String, _ values: [SQLiteValue] = []) throws -> [[String: SQLiteValue]] {
        let statement = try prepare(sql)
        defer { sqlite3_finalize(statement) }
        try bind(values, to: statement)
        var result: [[String: SQLiteValue]] = []
        while true {
            let code = sqlite3_step(statement)
            if code == SQLITE_DONE { return result }
            guard code == SQLITE_ROW else { throw lastError() }
            var row: [String: SQLiteValue] = [:]
            for index in 0..<sqlite3_column_count(statement) {
                let name = String(cString: sqlite3_column_name(statement, index))
                switch sqlite3_column_type(statement, index) {
                case SQLITE_INTEGER: row[name] = .integer(sqlite3_column_int64(statement, index))
                case SQLITE_FLOAT: row[name] = .double(sqlite3_column_double(statement, index))
                case SQLITE_TEXT:
                    row[name] = .text(String(cString: sqlite3_column_text(statement, index)))
                default: row[name] = .null
                }
            }
            result.append(row)
        }
    }

    func scalarInt(_ sql: String, _ values: [SQLiteValue] = []) throws -> Int64? {
        guard let value = try rows(sql, values).first?.values.first else { return nil }
        return value.int
    }

    func columns(in table: String) throws -> Set<String> {
        Set(try rows("PRAGMA table_info(\(quoteIdentifier(table)))").compactMap { $0["name"]?.string })
    }

    func tables() throws -> Set<String> {
        Set(try rows("SELECT name FROM sqlite_master WHERE type='table'").compactMap { $0["name"]?.string })
    }

    var lastInsertID: Int64 { sqlite3_last_insert_rowid(handle) }

    func transaction<T>(_ body: () throws -> T) throws -> T {
        try execute("BEGIN IMMEDIATE")
        do {
            let result = try body()
            try execute("COMMIT")
            return result
        } catch {
            try? execute("ROLLBACK")
            throw error
        }
    }

    private func prepare(_ sql: String) throws -> OpaquePointer {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(handle, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else { throw lastError() }
        return statement
    }

    private func bind(_ values: [SQLiteValue], to statement: OpaquePointer) throws {
        for (offset, value) in values.enumerated() {
            let index = Int32(offset + 1)
            let code: Int32
            switch value {
            case .integer(let number): code = sqlite3_bind_int64(statement, index, number)
            case .double(let number): code = sqlite3_bind_double(statement, index, number)
            case .text(let text): code = sqlite3_bind_text(statement, index, text, -1, SQLITE_TRANSIENT)
            case .null: code = sqlite3_bind_null(statement, index)
            }
            guard code == SQLITE_OK else { throw lastError() }
        }
    }

    private func lastError() -> Z21Error {
        .database(handle.map { String(cString: sqlite3_errmsg($0)) } ?? "Unknown SQLite error")
    }
}

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

func quoteIdentifier(_ value: String) -> String {
    "\"" + value.replacingOccurrences(of: "\"", with: "\"\"") + "\""
}

extension SQLiteValue {
    var string: String? {
        switch self {
        case .text(let value): return value
        case .integer(let value): return String(value)
        case .double(let value): return String(value)
        case .null: return nil
        }
    }
    var int: Int64? {
        switch self {
        case .integer(let value): return value
        case .double(let value): return Int64(value)
        case .text(let value): return Int64(value)
        case .null: return nil
        }
    }
    var double: Double? {
        switch self {
        case .double(let value): return value
        case .integer(let value): return Double(value)
        case .text(let value): return Double(value)
        case .null: return nil
        }
    }
}
