/// A "thinking" label (DESIGN.md §5): the text with a narrow, lighter band
/// sweeping across its letters, once every 1.5 s, looping, so the letters
/// lighten for a moment as it passes. It marks the one label of a turn that
/// is still working: the assistant's current step or its wait for the next
/// result. The band is the resting colour mixed toward the paper, and it is
/// narrow, so most of the label stays at full contrast at any moment. Under
/// reduced motion the text is static and no ticker runs.
library;

import 'package:flutter/widgets.dart';

import '../theme/delphos_colors.dart';

/// Text with a looping highlight sweep over its letters.
class ShimmerText extends StatefulWidget {
  const ShimmerText(this.text, {super.key, required this.style});

  /// The label; the colour of [style] is the resting colour of the letters.
  final String text;
  final TextStyle style;

  /// One pass of the band across the text.
  static const Duration period = Duration(milliseconds: 1500);

  @override
  State<ShimmerText> createState() => _ShimmerTextState();
}

class _ShimmerTextState extends State<ShimmerText>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: ShimmerText.period,
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.maybeDisableAnimationsOf(context) ?? false) {
      _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final label = Text(widget.text, style: widget.style);
    if (MediaQuery.maybeDisableAnimationsOf(context) ?? false) return label;
    final resting = widget.style.color ?? DelphosColors.ink3;
    final band = Color.lerp(resting, DelphosColors.canvas, 0.75)!;
    return AnimatedBuilder(
      animation: _controller,
      child: label,
      builder: (context, child) => ShaderMask(
        blendMode: BlendMode.srcIn,
        shaderCallback: (bounds) => LinearGradient(
          colors: [resting, band, resting],
          stops: const [0.42, 0.5, 0.58],
          transform: _Sweep(_controller.value * 2 - 1),
        ).createShader(bounds),
        child: child,
      ),
    );
  }
}

/// Slides the gradient by [offset] widths of the text: -1 puts the band left
/// of the text and 1 puts it right of it.
class _Sweep extends GradientTransform {
  const _Sweep(this.offset);

  final double offset;

  @override
  Matrix4? transform(Rect bounds, {TextDirection? textDirection}) =>
      Matrix4.translationValues(bounds.width * offset, 0, 0);
}
