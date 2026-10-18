// TARSKit wraps Apple frameworks only (EventKit, Contacts, UserNotifications, AppleScript).
// Each service is a small protocol with a testable fake. Services arrive in M1; this file
// carries the identifiers every service shares.

import Foundation

/// Identifiers fixed for the life of the project. TCC grants are keyed on the bundle id, so it never changes.
public enum TARSIdentity {
  public static let bundleIdentifier: String = "com.zararutherford.tars"
  public static let keychainService: String = "com.zararutherford.tars"
  public static let version: String = "0.0.1"
}

/// Where the daemon's socket lives. The Swift side is a pure client of it.
public enum TARSPaths {
  public static func dataDirectory(
    environment: [String: String] = ProcessInfo.processInfo.environment
  )
    -> URL
  {
    if let override: String = environment["TARS_DATA_DIR"], !override.isEmpty {
      return URL(fileURLWithPath: (override as NSString).expandingTildeInPath, isDirectory: true)
    }
    let appSupport: URL = FileManager.default.urls(
      for: .applicationSupportDirectory, in: .userDomainMask)[0]
    return appSupport.appendingPathComponent("TARS", isDirectory: true)
  }

  public static func daemonSocket(
    environment: [String: String] = ProcessInfo.processInfo.environment
  )
    -> URL
  {
    dataDirectory(environment: environment)
      .appendingPathComponent("run", isDirectory: true)
      .appendingPathComponent("daemon.sock", isDirectory: false)
  }
}
