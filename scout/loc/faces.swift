// Her görsel için: dosya<TAB>en büyük yüzün yüksekliği (görsel yüksekliğine oran)<TAB>yüz sayısı
import Foundation
import Vision
for p in CommandLine.arguments.dropFirst() {
    let req = VNDetectFaceRectanglesRequest()
    let h = VNImageRequestHandler(url: URL(fileURLWithPath: p))
    try? h.perform([req])
    let faces = (req.results ?? []).filter { $0.confidence > 0.5 }
    let big = faces.map { Double($0.boundingBox.height) }.max() ?? 0
    print("\(p)\t\(String(format: "%.3f", big))\t\(faces.count)")
}
