// StandFolderImport.swift
// "Bring your scores from another app": a folder chosen in Files (another score app's folder, or any
// folder of PDFs) is listed here, and the page reads its files one at a time straight from where
// they are (stand://…/__picked/…), so a library of thousands of PDFs is never copied twice or held in
// memory at once. Its sub-folders come along as names, for the page to make folders of them.

import Foundation
import UIKit
import UniformTypeIdentifiers

/// The folder the person chose, kept open (security scope) while the page reads from it.
var standPickedFolder: URL?
/// Several folders chosen at once: each by its name (the first part of what the page asks for).
var standPickedRoots: [String: URL] = [:]

final class StandFolderImport: NSObject, UIDocumentPickerDelegate {
    static let shared = StandFolderImport()
    private var onList: (([String: Any]) -> Void)?
    private static let kinds: Set<String> = ["pdf", "jpg", "jpeg", "png", "heic", "heif", "tif", "tiff", "zip", "4sb", "4sc", "standbackup"]

    func pick(from vc: UIViewController, onList: @escaping ([String: Any]) -> Void) {
        self.onList = onList
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.folder], asCopy: false)
        picker.delegate = self
        // (one folder or several: inside a folder, "Open" takes that folder; in a list, "Select"
        // then the folders, then "Open")
        picker.allowsMultipleSelection = true
        vc.present(picker, animated: true)
    }

    // (the simulator self-test only: a folder inside Stand's Documents, as if chosen in Files)
    func pickForTest(_ rel: String, onList: @escaping ([String: Any]) -> Void) {
        guard ProcessInfo.processInfo.arguments.contains("-standSelfTest"),
              let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first else { onList(["cancelled": true]); return }
        // (several folders: "a|b", as if chosen together)
        if rel.contains("|") {
            self.onList = onList
            let urls = rel.split(separator: "|").map { docs.appendingPathComponent(String($0), isDirectory: true) }
            documentPicker(UIDocumentPickerViewController(forOpeningContentTypes: [.folder]), didPickDocumentsAt: urls)
            return
        }
        let url = docs.appendingPathComponent(rel, isDirectory: true)
        for (_, u) in standPickedRoots { u.stopAccessingSecurityScopedResource() }
        standPickedRoots = [:]
        standPickedFolder = url
        DispatchQueue.global(qos: .userInitiated).async { let list = Self.list(url); DispatchQueue.main.async { onList(list) } }
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        guard let url = urls.first else { onList?(["cancelled": true]); return }
        if let old = standPickedFolder { old.stopAccessingSecurityScopedResource() }
        for (_, u) in standPickedRoots { u.stopAccessingSecurityScopedResource() }
        standPickedRoots = [:]; standPickedFolder = nil
        let reply = onList
        if urls.count == 1 {
            _ = url.startAccessingSecurityScopedResource()
            standPickedFolder = url
            DispatchQueue.global(qos: .userInitiated).async {
                let list = Self.list(url)
                DispatchQueue.main.async { reply?(list) }
            }
            return
        }
        // several folders: each comes in as a folder of its own name
        var roots: [String: URL] = [:]
        for u in urls {
            _ = u.startAccessingSecurityScopedResource()
            var name = u.lastPathComponent, n = 2
            while roots[name] != nil { name = "\(u.lastPathComponent) \(n)"; n += 1 }
            roots[name] = u
        }
        standPickedRoots = roots
        DispatchQueue.global(qos: .userInitiated).async {
            var files: [[String: Any]] = []; var notHere = 0
            for (name, u) in roots.sorted(by: { $0.key.localizedStandardCompare($1.key) == .orderedAscending }) {
                let l = Self.list(u)
                notHere += l["notHere"] as? Int ?? 0
                for f in l["files"] as? [[String: Any]] ?? [] { var g = f; g["rel"] = name + "/" + (f["rel"] as? String ?? ""); files.append(g) }
            }
            DispatchQueue.main.async { reply?(["name": "", "files": files, "notHere": notHere]) }
        }
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        onList?(["cancelled": true])
    }

    private static func list(_ root: URL) -> [String: Any] {
        var files: [[String: Any]] = []
        var notHere = 0
        let keys: [URLResourceKey] = [.isRegularFileKey, .fileSizeKey, .ubiquitousItemDownloadingStatusKey]
        let base = root.resolvingSymlinksInPath().standardizedFileURL.path
        let en = FileManager.default.enumerator(at: root, includingPropertiesForKeys: keys, options: [.skipsPackageDescendants])
        while let f = en?.nextObject() as? URL {
            let name = f.lastPathComponent
            // (a file kept only in iCloud shows here as ".Name.pdf.icloud": it is asked for, and counted)
            if name.hasPrefix(".") {
                if name.hasSuffix(".icloud") { notHere += 1; try? FileManager.default.startDownloadingUbiquitousItem(at: f) }
                continue
            }
            guard kinds.contains(f.pathExtension.lowercased()) else { continue }
            let v = try? f.resourceValues(forKeys: Set(keys))
            guard v?.isRegularFile == true else { continue }
            var rel = f.resolvingSymlinksInPath().standardizedFileURL.path
            if rel.hasPrefix(base) { rel = String(rel.dropFirst(base.count)) }
            while rel.hasPrefix("/") { rel.removeFirst() }
            files.append(["rel": rel, "size": v?.fileSize ?? 0])
            if files.count >= 20000 { break }
        }
        files.sort { ($0["rel"] as? String ?? "").localizedStandardCompare($1["rel"] as? String ?? "") == .orderedAscending }
        return ["name": root.lastPathComponent, "files": files, "notHere": notHere]
    }
}
