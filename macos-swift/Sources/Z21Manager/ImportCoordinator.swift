import Foundation

@MainActor
final class ImportCoordinator {
    var pendingLocomotive: Locomotive?

    func targetIndex(for session: ImportReviewSession?, in locomotives: [Locomotive]) -> Int? {
        guard let targetID = session?.targetID else { return nil }
        return locomotives.firstIndex { $0.id == targetID }
    }

    func fieldChanges(from current: Locomotive, to proposed: Locomotive) -> [ImportFieldChange] {
        let values: [(String, String, String, String)] = [
            ("name", "Name", current.name, proposed.name),
            ("address", "Address", String(current.address), String(proposed.address)),
            ("speed", "Max Speed", String(current.speed), String(proposed.speed)),
            ("speedDisplay", "Speed Display", String(current.speedDisplay), String(proposed.speedDisplay)),
            ("fullName", "Full Name", current.fullName, proposed.fullName),
            ("railway", "Railway", current.railway, proposed.railway),
            ("articleNumber", "Article Number", current.articleNumber, proposed.articleNumber),
            ("decoderType", "Decoder / Interface", current.decoderType, proposed.decoderType),
            ("buildYear", "Build Year", current.buildYear, proposed.buildYear),
            ("modelBufferLength", "Model Buffer Length", current.modelBufferLength, proposed.modelBufferLength),
            ("serviceWeight", "Service Weight", current.serviceWeight, proposed.serviceWeight),
            ("modelWeight", "Model Weight", current.modelWeight, proposed.modelWeight),
            ("rmin", "Minimum Radius", current.rmin, proposed.rmin),
            ("ip", "IP Address", current.ip, proposed.ip),
            ("driversCab", "Driver’s Cab", current.driversCab, proposed.driversCab),
            ("description", "Description", current.description, proposed.description)
        ]
        return values.compactMap { key, label, old, new in
            old == new ? nil : ImportFieldChange(id: key, label: label, current: old, proposed: new)
        }
    }

    func applyField(_ key: String, from source: Locomotive, to target: inout Locomotive) {
        switch key {
        case "name": target.name = source.name
        case "address": target.address = source.address
        case "speed": target.speed = source.speed
        case "speedDisplay": target.speedDisplay = source.speedDisplay
        case "fullName": target.fullName = source.fullName
        case "railway": target.railway = source.railway
        case "articleNumber": target.articleNumber = source.articleNumber
        case "decoderType": target.decoderType = source.decoderType
        case "buildYear": target.buildYear = source.buildYear
        case "modelBufferLength": target.modelBufferLength = source.modelBufferLength
        case "serviceWeight": target.serviceWeight = source.serviceWeight
        case "modelWeight": target.modelWeight = source.modelWeight
        case "rmin": target.rmin = source.rmin
        case "ip": target.ip = source.ip
        case "driversCab": target.driversCab = source.driversCab
        case "description": target.description = source.description
        default: break
        }
    }

    func reset() {
        pendingLocomotive = nil
    }
}
