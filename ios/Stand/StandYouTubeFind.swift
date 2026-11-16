import Foundation

// Listen → YouTube: the performances found for a piece (and a performer), so the right one is
// chosen in Stand and plays over the score, instead of leaving for YouTube. YouTube's own search
// page is read (what the browser would show): the videos in their order, each with its title,
// channel, length and picture. Nothing is sent but the words searched for.
enum StandYouTubeFind {
    static func search(_ q: String, done: @escaping ([[String: Any]]?) -> Void) {
        var c = URLComponents(string: "https://www.youtube.com/results")!
        c.queryItems = [URLQueryItem(name: "search_query", value: q), URLQueryItem(name: "hl", value: "en")]
        guard let url = c.url else { done(nil); return }
        var r = URLRequest(url: url, timeoutInterval: 12)
        r.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15", forHTTPHeaderField: "User-Agent")
        r.setValue("en", forHTTPHeaderField: "Accept-Language")
        // (in Europe YouTube first asks about cookies; this says it was answered, with none kept)
        r.setValue("SOCS=CAI; CONSENT=PENDING+987", forHTTPHeaderField: "Cookie")
        r.httpShouldHandleCookies = false
        URLSession.shared.dataTask(with: r) { data, _, _ in
            let items = data.flatMap { String(data: $0, encoding: .utf8) }.flatMap(parse)
            DispatchQueue.main.async { done(items) }
        }.resume()
    }

    // ytInitialData: the page's own description of what it shows
    static func parse(_ html: String) -> [[String: Any]]? {
        let marks = ["var ytInitialData = ", "window[\"ytInitialData\"] = ", "ytInitialData = "]
        guard let m = marks.lazy.compactMap({ html.range(of: $0) }).first else { return nil }
        let rest = html[m.upperBound...]
        guard let end = rest.range(of: ";</script>") else { return nil }
        guard let d = String(rest[..<end.lowerBound]).data(using: .utf8),
              let root = try? JSONSerialization.jsonObject(with: d) else { return nil }
        var out: [[String: Any]] = [], seen = Set<String>()
        walk(root) { v in
            guard out.count < 12, let id = v["videoId"] as? String, id.count == 11, !seen.contains(id) else { return }
            // (live streams and Shorts have no length shown: left out)
            guard let len = (v["lengthText"] as? [String: Any])?["simpleText"] as? String else { return }
            seen.insert(id)
            out.append([
                "id": id,
                "title": text(v["title"]),
                "by": text(v["ownerText"]).isEmpty ? text(v["longBylineText"]) : text(v["ownerText"]),
                "len": len,
                "views": text(v["shortViewCountText"]),
                "pic": "https://i.ytimg.com/vi/\(id)/mqdefault.jpg",
            ])
        }
        return out
    }

    // the videos, in the order the page shows them
    private static func walk(_ x: Any, _ f: ([String: Any]) -> Void) {
        if let d = x as? [String: Any] {
            if let v = d["videoRenderer"] as? [String: Any] { f(v); return }
            for k in d.keys.sorted(by: { order($0) < order($1) }) { walk(d[k]!, f) }
        } else if let a = x as? [Any] {
            for e in a { walk(e, f) }
        }
    }
    // (the results themselves before anything beside them)
    private static func order(_ k: String) -> Int { k == "contents" ? 0 : k == "primaryContents" ? 0 : 1 }

    private static func text(_ x: Any?) -> String {
        guard let d = x as? [String: Any] else { return "" }
        if let s = d["simpleText"] as? String { return s }
        if let runs = d["runs"] as? [[String: Any]] { return runs.compactMap { $0["text"] as? String }.joined() }
        return ""
    }
}
