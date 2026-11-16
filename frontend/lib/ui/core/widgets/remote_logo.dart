/// A club crest or league logo from the network, drawn at its own aspect
/// ratio with no ground or frame.
///
/// Like `PlayerAvatar`, it goes through `Image.network`, which fetches the
/// bytes and lets CanvasKit decode them (ADR-026): no HTML `<img>` platform
/// view. While it loads it reserves its height (not its width), so the line
/// it sits in does not reflow when the image arrives; if it fails it shows
/// nothing: never a broken image or a stand-in.
library;

import 'package:flutter/widgets.dart';

/// The logo at [url], [height] logical pixels tall.
class RemoteLogo extends StatelessWidget {
  const RemoteLogo({
    super.key,
    required this.url,
    required this.height,
    this.gapAfter = 0,
  });

  /// An allowed image URL, or `null` for no logo.
  final String? url;
  final double height;

  /// Space to the right of the logo, present only while the logo shows, so
  /// a missing logo leaves no gap before the name beside it.
  final double gapAfter;

  @override
  Widget build(BuildContext context) {
    final url = this.url;
    if (url == null) return const SizedBox.shrink();
    return Image.network(
      url,
      height: height,
      fit: BoxFit.contain,
      excludeFromSemantics: true,
      frameBuilder: (context, child, frame, wasSynchronouslyLoaded) =>
          frame == null && !wasSynchronouslyLoaded
          ? SizedBox(height: height)
          : Padding(
              padding: EdgeInsets.only(right: gapAfter),
              child: child,
            ),
      errorBuilder: (_, _, _) => const SizedBox.shrink(),
    );
  }
}
