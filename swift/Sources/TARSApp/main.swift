// TARS.app: an LSUIElement bundle that is the single TCC principal and the daemon's parent.
// M-1: it launches, logs, and idles. The socket client, command router and supervisor arrive in M1.

import AppKit
import TARSKit

final class AppDelegate: NSObject, NSApplicationDelegate {
  func applicationDidFinishLaunching(_ notification: Notification) {
    let socket: URL = TARSPaths.daemonSocket()
    NSLog("TARS.app \(TARSIdentity.version) launched; daemon socket at \(socket.path)")
  }

  func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
    false
  }
}

let app: NSApplication = NSApplication.shared
let delegate: AppDelegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
