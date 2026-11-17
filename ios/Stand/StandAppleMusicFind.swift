import Foundation

// Listen → Apple Music: the recordings found for a piece (and a performer), from Apple's own public
// search (the one the iTunes Store has always offered), in the iPad's own country. A recording
// chosen opens in the Music app, where a subscriber hears it whole. Nothing is sent but the words.
enum StandAppleMusicFind {
    static func search(_ q: String, done: @escaping ([[String: Any]]?) -> Void) {
        var c = URLComponents(string: "https://itunes.apple.com/search")!
        let cc = (Locale.current.region?.identifier ?? "US").lowercased()
        c.queryItems = [
            URLQueryItem(name: "term", value: q), URLQueryItem(name: "media", value: "music"),
            URLQueryItem(name: "entity", value: "song"), URLQueryItem(name: "limit", value: "25"),
            URLQueryItem(name: "country", value: cc),
        ]
        guard let url = c.url else { done(nil); return }
        URLSession.shared.dataTask(with: URLRequest(url: url, timeoutInterval: 12)) { data, _, _ in
            var out: [[String: Any]]? = nil
            if let data, let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let res = root["results"] as? [[String: Any]] {
                var seen = Set<String>()
                out = res.compactMap { r in
                    guard let link = r["trackViewUrl"] as? String, let name = r["trackName"] as? String,
                          let id = r["trackId"] as? Int, !seen.contains(String(id)) else { return nil }
                    seen.insert(String(id))
                    let ms = r["trackTimeMillis"] as? Int ?? 0, s = ms / 1000
                    let pic = (r["artworkUrl100"] as? String ?? "").replacingOccurrences(of: "100x100", with: "200x200")
                    return ["id": String(id), "title": name, "by": r["artistName"] as? String ?? "",
                            "album": r["collectionName"] as? String ?? "",
                            "len": s > 0 ? String(format: "%d:%02d", s / 60, s % 60) : "",
                            "pic": pic, "url": link]
                }
            }
            DispatchQueue.main.async { done(out) }
        }.resume()
    }
}
