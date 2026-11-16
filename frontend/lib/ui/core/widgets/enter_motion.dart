/// A one-shot entry for a widget (DESIGN.md §5): opacity 0 to 1 and a short
/// slide from [offset] to rest, once, when the widget is first built, after
/// an optional [delay]. It marks a view change, or one item of a staggered
/// first load. It never repeats, and it is instant under reduced motion.
library;

import 'package:flutter/widgets.dart';

import '../theme/motion.dart';

/// Plays the entry when first built; rebuilds with new arguments do not
/// replay it, and neither does [animate] changing later. With [animate]
/// false at first build the child is shown as is.
class EnterMotion extends StatefulWidget {
  const EnterMotion({
    super.key,
    required this.child,
    this.offset = Offset.zero,
    this.delay = Duration.zero,
    this.duration = DelphosMotion.enter,
    this.animate = true,
  });

  final Widget child;

  /// Where the child starts, relative to its resting place, in logical pixels.
  final Offset offset;
  final Duration delay;
  final Duration duration;
  final bool animate;

  @override
  State<EnterMotion> createState() => _EnterMotionState();
}

class _EnterMotionState extends State<EnterMotion>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    value: 1,
  );
  late final Animation<double> _curve;
  bool _decided = false;
  bool _animated = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_decided) return;
    _decided = true;
    _animated = widget.animate;
    if (!_animated) return;
    final delay = DelphosMotion.duration(context, widget.delay);
    final duration = DelphosMotion.duration(context, widget.duration);
    final total = delay + duration;
    final begin = total == Duration.zero
        ? 0.0
        : delay.inMicroseconds / total.inMicroseconds;
    _controller.duration = total;
    // The delay is the first part of the timeline, so one controller carries
    // both, and a zero total (reduced motion) is simply done.
    _curve = CurvedAnimation(
      parent: _controller,
      curve: Interval(begin, 1, curve: DelphosMotion.easeOut),
    );
    if (total > Duration.zero) _controller.forward(from: 0);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_animated) return widget.child;
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        final t = _curve.value;
        return Opacity(
          opacity: t,
          child: Transform.translate(
            offset: widget.offset * (1 - t),
            child: child,
          ),
        );
      },
      child: widget.child,
    );
  }
}
