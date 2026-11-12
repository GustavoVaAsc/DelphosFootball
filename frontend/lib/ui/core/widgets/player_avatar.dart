/// A player's portrait with the club crest disc over its corner
/// (DESIGN.md §1 badge hierarchy; 44 px in the table, 64 px in the dossier).
///
/// Portraits and crests are the dataset's own Transfermarkt URLs, the only
/// third-party requests the app makes, and only after `allowedImageUrl`
/// (ADR-026). Both hosts answer with `Access-Control-Allow-Origin: *`, so
/// `Image.network` fetches the bytes and CanvasKit decodes them: no HTML
/// `<img>` platform views, which would cost one platform view per image in
/// a 50-row table.
library;

import 'package:material_ui/material_ui.dart';

import '../theme/delphos_colors.dart';

/// The round portrait and, when [crestUrl] is set, the crest disc.
class PlayerAvatar extends StatelessWidget {
  const PlayerAvatar({
    super.key,
    required this.imageUrl,
    this.crestUrl,
    this.size = 44,
    this.crestSize = 20,
  });

  /// The dossier size: 64 px portrait, 24 px crest.
  const PlayerAvatar.large({super.key, required this.imageUrl, this.crestUrl})
    : size = 64,
      crestSize = 24;

  final String? imageUrl;
  final String? crestUrl;
  final double size;
  final double crestSize;

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: SizedBox.square(
        dimension: size,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            Positioned.fill(child: _Portrait(url: imageUrl)),
            if (crestUrl case final url?)
              Positioned(
                right: -2,
                bottom: -2,
                child: _Crest(url: url, size: crestSize),
              ),
          ],
        ),
      ),
    );
  }
}

class _Portrait extends StatelessWidget {
  const _Portrait({required this.url});

  final String? url;

  static const Widget _placeholder = ColoredBox(
    color: DelphosColors.surfaceMuted,
  );

  @override
  Widget build(BuildContext context) {
    final url = this.url;
    return Container(
      foregroundDecoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: DelphosColors.rule),
      ),
      child: ClipOval(
        child: url == null
            ? _placeholder
            : Image.network(
                url,
                fit: BoxFit.cover,
                errorBuilder: (_, _, _) => _placeholder,
              ),
      ),
    );
  }
}

class _Crest extends StatelessWidget {
  const _Crest({required this.url, required this.size});

  final String url;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: DelphosColors.surface,
        border: Border.all(color: DelphosColors.rule),
        boxShadow: const [
          BoxShadow(
            color: DelphosColors.floatShadow,
            offset: Offset(0, 1),
            blurRadius: 2,
          ),
        ],
      ),
      child: Image.network(
        url,
        fit: BoxFit.contain,
        errorBuilder: (_, _, _) => const SizedBox.shrink(),
      ),
    );
  }
}
