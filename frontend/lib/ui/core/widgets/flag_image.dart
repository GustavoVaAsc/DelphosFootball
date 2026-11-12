/// A country flag from the bundled set (ADR-026), never from the network.
library;

import 'package:material_ui/material_ui.dart';

import '../labels/countries.dart';

/// The flag of a dataset country, 16 x 12 by default, with its Spanish name
/// as the accessible label and tooltip. An unmapped country, or one whose
/// flag would be wrong, renders nothing (DESIGN.md §4, Flags).
class FlagImage extends StatelessWidget {
  const FlagImage({
    super.key,
    required this.country,
    this.width = 16,
    this.height = 12,
  });

  /// The dataset's English `country_of_citizenship`.
  final String? country;
  final double width;
  final double height;

  @override
  Widget build(BuildContext context) {
    final code = countryFlagCode(country);
    final name = countryNameEs(country);
    if (code == null || name == null) return const SizedBox.shrink();
    return Tooltip(
      message: name,
      excludeFromSemantics: true,
      child: Image.asset(
        'assets/flags/$code.png',
        width: width,
        height: height,
        fit: BoxFit.cover,
        semanticLabel: 'Bandera de $name',
        errorBuilder: (_, _, _) => const SizedBox.shrink(),
      ),
    );
  }
}
