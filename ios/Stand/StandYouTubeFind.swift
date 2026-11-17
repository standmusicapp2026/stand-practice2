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
        // (YouTube now and then answers with a page laid out otherwise, or with nothing in it: asked
        // once more before saying nothing was found)
        func ask(_ again: Bool) {
            URLSession.shared.dataTask(with: r) { data, _, _ in
                let items = data.flatMap { String(data: $0, encoding: .utf8) }.flatMap(parse)
                if again && (items?.isEmpty ?? true) { ask(false); return }
                DispatchQueue.main.async { done(items) }
            }.resume()
        }
        ask(true)
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
        // (each video laid out one of two ways: the older "videoRenderer", the newer "lockup")
        walk(root) { v, lockup in
            guard out.count < 12 else { return }
            if lockup {
                guard let id = v["contentId"] as? String, id.count == 11, !seen.contains(id),
                      (v["contentType"] as? String ?? "VIDEO").contains("VIDEO") else { return }
                let md = (v["metadata"] as? [String: Any])?["lockupMetadataViewModel"] as? [String: Any]
                let title = ((md?["title"] as? [String: Any])?["content"] as? String) ?? ""
                var parts: [String] = []
                collect(md?["metadata"]) { d in if let t = (d["text"] as? [String: Any])?["content"] as? String { parts.append(t) } }
                var len = ""
                collect(v["contentImage"]) { d in
                    if len.isEmpty, let b = d["thumbnailBadgeViewModel"] as? [String: Any], let t = b["text"] as? String,
                       t.range(of: "^\\d+(:\\d\\d)+$", options: .regularExpression) != nil { len = t }
                }
                // (live streams and Shorts have no length shown: left out)
                guard !title.isEmpty, !len.isEmpty else { return }
                seen.insert(id)
                out.append(["id": id, "title": title, "by": parts.first ?? "", "len": len,
                            "views": parts.first(where: { $0.lowercased().contains("view") }) ?? "",
                            "pic": "https://i.ytimg.com/vi/\(id)/mqdefault.jpg"])
            } else {
                guard let id = v["videoId"] as? String, id.count == 11, !seen.contains(id) else { return }
                // (live streams and Shorts have no length shown: left out)
                guard let len = (v["lengthText"] as? [String: Any])?["simpleText"] as? String else { return }
                seen.insert(id)
                out.append(["id": id, "title": text(v["title"]),
                            "by": text(v["ownerText"]).isEmpty ? text(v["longBylineText"]) : text(v["ownerText"]),
                            "len": len, "views": text(v["shortViewCountText"]),
                            "pic": "https://i.ytimg.com/vi/\(id)/mqdefault.jpg"])
            }
        }
        return out
    }

    // the videos, in the order the page shows them
    private static func walk(_ x: Any, _ f: ([String: Any], Bool) -> Void) {
        if let d = x as? [String: Any] {
            if let v = d["videoRenderer"] as? [String: Any] { f(v, false); return }
            if let v = d["lockupViewModel"] as? [String: Any] { f(v, true); return }
            for k in d.keys.sorted(by: { order($0) < order($1) }) { walk(d[k]!, f) }
        } else if let a = x as? [Any] {
            for e in a { walk(e, f) }
        }
    }
    // every dictionary inside, in order
    private static func collect(_ x: Any?, _ f: ([String: Any]) -> Void) {
        if let d = x as? [String: Any] { f(d); for k in d.keys.sorted() { collect(d[k], f) } }
        else if let a = x as? [Any] { for e in a { collect(e, f) } }
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
