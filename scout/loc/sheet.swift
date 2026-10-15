// Pafta: sheet <çıktı.jpg> <no:dosya>... (8 sütun, 2:3 hücre, ortadan kırpılmış, numaralı)
import Foundation
import CoreGraphics
import ImageIO
import AppKit
let args = Array(CommandLine.arguments.dropFirst())
let out = args[0]; let items = args.dropFirst().map { $0.split(separator: ":", maxSplits: 1).map(String.init) }
let TW = 180, TH = 270, G = 4, COLS = 8
let rows = (items.count + COLS - 1) / COLS
let W = COLS * (TW + G), H = rows * (TH + G)
let ctx = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
ctx.setFillColor(CGColor(gray: 1, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: W, height: H))
NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: false)
for (k, it) in items.enumerated() {
    guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: it[1]) as CFURL, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else { continue }
    let w = Double(img.width), h = Double(img.height)
    let cw = min(w, h * 2 / 3), ch = min(h, w * 3 / 2)
    let crop = img.cropping(to: CGRect(x: (w - cw) / 2, y: (h - ch) / 2, width: cw, height: ch))!
    let x = (k % COLS) * (TW + G), y = H - (k / COLS + 1) * (TH + G)
    ctx.draw(crop, in: CGRect(x: x, y: y, width: TW, height: TH))
    ctx.setFillColor(CGColor(gray: 0, alpha: 1)); ctx.fill(CGRect(x: x, y: y + TH - 24, width: 44, height: 24))
    (it[0] as NSString).draw(at: NSPoint(x: x + 4, y: y + TH - 21), withAttributes: [.font: NSFont.boldSystemFont(ofSize: 15), .foregroundColor: NSColor.white])
}
let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: out) as CFURL, "public.jpeg" as CFString, 1, nil)!
CGImageDestinationAddImage(dest, ctx.makeImage()!, [kCGImageDestinationLossyCompressionQuality: 0.8] as CFDictionary)
CGImageDestinationFinalize(dest)
