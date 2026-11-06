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

final class StandFolderImport: NSObject, UIDocumentPickerDelegate {
    static let shared = StandFolderImport()
    private var onList: (([String: Any]) -> Void)?
    private static let kinds: Set<String> = ["pdf", "jpg", "jpeg", "png", "heic", "heif", "tif", "tiff", "zip", "4sb", "4sc", "standbackup"]

    func pick(from vc: UIViewController, onList: @escaping ([String: Any]) -> Void) {
        self.onList = onList
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.folder], asCopy: false)
        picker.delegate = self
        picker.allowsMultipleSelection = false
        vc.present(picker, animated: true)
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        guard let url = urls.first else { onList?(["cancelled": true]); return }
        if let old = standPickedFolder { old.stopAccessingSecurityScopedResource() }
        _ = url.startAccessingSecurityScopedResource()
        standPickedFolder = url
        let reply = onList
        DispatchQueue.global(qos: .userInitiated).async {
            let list = Self.list(url)
            DispatchQueue.main.async { reply?(list) }
        }
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        onList?(["cancelled": true])
    }

    private static func list(_ root: URL) -> [String: Any] {
        var files: [[String: Any]] = []
        var notHere = 0
        let keys: [URLResourceKey] = [.isRegularFileKey, .fileSizeKey, .ubiquitousItemDownloadingStatusKey]
        let base = root.standardizedFileURL.path
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
            var rel = f.standardizedFileURL.path
            if rel.hasPrefix(base) { rel = String(rel.dropFirst(base.count)) }
            while rel.hasPrefix("/") { rel.removeFirst() }
            files.append(["rel": rel, "size": v?.fileSize ?? 0])
            if files.count >= 20000 { break }
        }
        files.sort { ($0["rel"] as? String ?? "").localizedStandardCompare($1["rel"] as? String ?? "") == .orderedAscending }
        return ["name": root.lastPathComponent, "files": files, "notHere": notHere]
    }
}
