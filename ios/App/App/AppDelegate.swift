import UIKit
import Capacitor
import AVFoundation
import WebKit

@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {

    var window: UIWindow?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // Mini Fighter: game sound plays like a game (category playback: ignores the silent switch, does not mix
        // with other apps' audio), set at launch and again after anything that may change it
        MFAudio.setPlayback("launch")
        let nc = NotificationCenter.default
        nc.addObserver(forName: AVAudioSession.interruptionNotification, object: nil, queue: .main) { note in
            let raw = note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt
            if raw == AVAudioSession.InterruptionType.ended.rawValue { MFAudio.setPlayback("interruption ended") }
        }
        nc.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil, queue: .main) { _ in
            MFAudio.setPlayback("active")
        }
        return true
    }

    func applicationWillResignActive(_ application: UIApplication) {
        // Sent when the application is about to move from active to inactive state. This can occur for certain types of temporary interruptions (such as an incoming phone call or SMS message) or when the user quits the application and it begins the transition to the background state.
        // Use this method to pause ongoing tasks, disable timers, and invalidate graphics rendering callbacks. Games should use this method to pause the game.
    }

    func applicationDidEnterBackground(_ application: UIApplication) {
        // Use this method to release shared resources, save user data, invalidate timers, and store enough application state information to restore your application to its current state in case it is terminated later.
        // If your application supports background execution, this method is called instead of applicationWillTerminate: when the user quits.
    }

    func applicationWillEnterForeground(_ application: UIApplication) {
        // Called as part of the transition from the background to the active state; here you can undo many of the changes made on entering the background.
    }

    func applicationDidBecomeActive(_ application: UIApplication) {
        // Restart any tasks that were paused (or not yet started) while the application was inactive. If the application was previously in the background, optionally refresh the user interface.
    }

    func applicationWillTerminate(_ application: UIApplication) {
        // Called when the application is about to terminate. Save data if appropriate. See also applicationDidEnterBackground:.
    }

    func application(_ application: UIApplication,
                     configurationForConnecting connectingSceneSession: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        let config = UISceneConfiguration(name: "Default Configuration",
                                          sessionRole: connectingSceneSession.role)
        config.delegateClass = SceneDelegate.self
        return config
    }
}

// MARK: - Mini Fighter audio session

enum MFAudio {
    /// .playback, mode default, no options (mixWithOthers off), then active
    static func setPlayback(_ why: String) {
        let session = AVAudioSession.sharedInstance()
        do {
            if session.category != .playback || !session.categoryOptions.isEmpty {
                try session.setCategory(.playback, mode: .default, options: [])
            }
            try session.setActive(true)
        } catch {
            NSLog("MFAudio: setPlayback (\(why)) failed: \(error.localizedDescription)")
        }
    }
}

/// window.Capacitor.Plugins.MFAudio.setPlayback(): the page calls it when an AdMob full-screen ad closes
/// (the Google Mobile Ads SDK may change the shared audio session while its ad plays)
@objc(MFAudioPlugin)
public class MFAudioPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "MFAudioPlugin"
    public let jsName = "MFAudio"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "setPlayback", returnType: CAPPluginReturnPromise)
    ]

    @objc func setPlayback(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            MFAudio.setPlayback(call.getString("reason") ?? "js")
            let s = AVAudioSession.sharedInstance()
            call.resolve(["category": s.category.rawValue, "mixWithOthers": s.categoryOptions.contains(.mixWithOthers)])
        }
    }
}

/// The app's bridge view controller (Main.storyboard): registers MFAudio and keeps inline media playback
/// without a user gesture explicit (Capacitor's default today)
class MFViewController: CAPBridgeViewController {
    override func capacitorDidLoad() {
        bridge?.registerPluginInstance(MFAudioPlugin())
    }

    override func webViewConfiguration(for instanceConfiguration: InstanceConfiguration) -> WKWebViewConfiguration {
        let c = super.webViewConfiguration(for: instanceConfiguration)
        c.allowsInlineMediaPlayback = true
        c.mediaTypesRequiringUserActionForPlayback = []
        return c
    }
}
