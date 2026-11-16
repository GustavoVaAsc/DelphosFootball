/// A figure that counts up from zero to its value once, when first built
/// (DESIGN.md §5): the dossier's two valuation figures. Every frame goes
/// through [format], the app's own es-ES formatter, and the width is fixed
/// to the widest text of the count, so the neighbours never jitter while the
/// digits change. It lands on exactly `format(value)`, and is instant under reduced
/// motion.
library;

import 'package:flutter/widgets.dart';

import '../theme/motion.dart';

/// `format(v)` for `v` rising from 0 to [value] over [duration].
class CountUpText extends StatelessWidget {
  const CountUpText({
    super.key,
    required this.value,
    required this.format,
    required this.style,
    this.duration = DelphosMotion.figures,
  });

  final double value;
  final String Function(double value) format;
  final TextStyle style;
  final Duration duration;

  /// The width of the widest text the count can show: the final one, or an
  /// intermediate one that is wider (a count to "€1,0 M" passes through
  /// "€999 mil"). Sampled along the way and just below the usual unit
  /// changes, so the box never grows or shrinks mid-count.
  double _widest(String finalText, TextScaler scaler) {
    final texts = {
      finalText,
      for (var i = 0; i < 16; i++) format(value * i / 16),
      for (final edge in const [999.0, 999499.0])
        if (edge < value) format(edge),
    };
    var widest = 0.0;
    for (final text in texts) {
      final painter = TextPainter(
        text: TextSpan(text: text, style: style),
        textDirection: TextDirection.ltr,
        textScaler: scaler,
      )..layout();
      if (painter.width > widest) widest = painter.width;
      painter.dispose();
    }
    return widest.ceilToDouble();
  }

  @override
  Widget build(BuildContext context) {
    final finalText = format(value);
    final width = _widest(finalText, MediaQuery.textScalerOf(context));
    return Semantics(
      label: finalText,
      excludeSemantics: true,
      child: TweenAnimationBuilder<double>(
        tween: Tween<double>(begin: 0, end: value),
        duration: DelphosMotion.duration(context, duration),
        curve: DelphosMotion.easeOut,
        builder: (context, current, _) => SizedBox(
          width: width,
          child: Text(
            // Exactly the final text at the end, whatever the float maths.
            current == value ? finalText : format(current),
            maxLines: 1,
            softWrap: false,
            overflow: TextOverflow.visible,
            style: style,
          ),
        ),
      ),
    );
  }
}
