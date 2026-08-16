import Foundation

enum FunctionMatcher {
    private static let phrases: [(String, [String])] = [
        ("door_close", ["close door", "tür schließen", "fermer porte", "open / close door"]),
        ("door_open", ["open door", "tür öffnen", "ouvrir porte"]),
        ("cockpit_light_left", ["cabin 1", "cab 1", "führerstand 1"]),
        ("cockpit_light_right", ["cabin 2", "cab 2", "führerstand 2"]),
        ("main_beam", ["high beam", "main beam", "fernlicht"]),
        ("interior_light", ["interior light", "innenbeleuchtung"]),
        ("couple", ["couple", "kupplung", "attelage"]),
        ("decouple", ["decouple", "entkuppeln", "dételage"]),
        ("compressor", ["compressor", "air conditioning", "kompressor"]),
        ("sanden", ["sanding", "sander", "sand", "sandstreuer", "sanden", "sablage", "撒砂", "撒沙"]),
        ("sound_brake", ["brake sound", "bremsenquietschen"]),
        ("sound2", ["driver noise", "driving noise", "driving sound", "fahrgeräusch", "fahrgerausch", "bruit de conduite"]),
        ("whistle_long", ["long whistle", "long horn"]),
        ("whistle_short", ["short whistle", "short horn"]),
        ("louder", ["volume increase", "louder", "lauter"]),
        ("quiter", ["volume decrease", "quieter", "leiser"]),
        ("mute", ["mute", "sound off", "stumm"]),
        ("bell", ["bell", "glocke"]),
        ("light", ["light", "licht", "éclairage"]),
        ("sound1", ["sound", "geräusch"])
    ]

    static func match(_ description: String, available: [String]) -> String {
        let normalized = description.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current).lowercased()
        let set = Set(available)
        for (icon, terms) in phrases where set.contains(icon) {
            if terms.contains(where: normalized.contains) { return icon }
        }
        let words = Set(normalized.split(whereSeparator: { !$0.isLetter && !$0.isNumber }).map(String.init))
        let scored = available.map { icon -> (String, Int) in
            let iconWords = Set(icon.replacingOccurrences(of: "_", with: " ").split(separator: " ").map(String.init))
            return (icon, words.intersection(iconWords).count)
        }.max { $0.1 < $1.1 }
        return scored?.1 ?? 0 > 0 ? scored!.0 : (set.contains("neutral") ? "neutral" : available.first ?? "")
    }

    static func shortcut(description: String, icon: String) -> String {
        let source = description.isEmpty ? icon.replacingOccurrences(of: "_", with: " ") : description
        let clean = source.filter { $0.isLetter || $0.isNumber || $0 == " " }
        let words = clean.split(separator: " ")
        if words.count > 1 {
            let joined = words.prefix(4).map { String($0.prefix(2)) }.joined()
            return String(joined.prefix(8))
        }
        return String(clean.prefix(icon == "neutral" ? 10 : 8))
    }

    static func buttonType(description: String, icon: String) -> Int {
        let value = description.lowercased()
        if value.contains("time") || value.contains("timed") { return 2 }
        if ["horn", "whistle", "couple", "decouple", "signal"].contains(where: { value.contains($0) || icon.contains($0) }) { return 1 }
        return 0
    }

    static func missingNumbers(_ functions: [FunctionInfo]) -> [Int] {
        let values = Set(functions.map(\.number))
        guard let low = values.min(), let high = values.max() else { return [] }
        return (low...high).filter { !values.contains($0) }
    }
}
