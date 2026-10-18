import Foundation
import Testing

@testable import TARSKit

@Test func bundleIdentifierIsFixed() {
  #expect(TARSIdentity.bundleIdentifier == "com.zararutherford.tars")
}

@Test func dataDirectoryHonorsEnvironment() {
  let dir: URL = TARSPaths.dataDirectory(environment: ["TARS_DATA_DIR": "/tmp/tars-test"])
  #expect(dir.path == "/tmp/tars-test")
  let sock: URL = TARSPaths.daemonSocket(environment: ["TARS_DATA_DIR": "/tmp/tars-test"])
  #expect(sock.path == "/tmp/tars-test/run/daemon.sock")
}

@Test func dataDirectoryDefaultsToApplicationSupport() {
  let dir: URL = TARSPaths.dataDirectory(environment: [:])
  #expect(dir.path.hasSuffix("/Library/Application Support/TARS"))
}
