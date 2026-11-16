/// The side panel's slot beside the table (DESIGN.md §4 and §5): 20 px gap
/// plus the 440 px dossier, which slides 16 px in from the right while it
/// fades in when it opens, and leaves the same way when it closes. The slot
/// keeps its width until the exit ends, then reports [onExited], so the panel
/// has its content on screen for the whole exit. Opening or closing never
/// moves focus; that stays with the explorer. Instant under reduced motion.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/motion.dart';

/// Holds [child] while [open], and through its exit.
class DossierSlot extends StatefulWidget {
  const DossierSlot({
    super.key,
    required this.open,
    required this.child,
    this.onExited,
  });

  final bool open;
  final Widget child;

  /// Called when a close has finished (or at once without animation).
  final VoidCallback? onExited;

  /// The slide distance.
  static const double slide = 16;

  @override
  State<DossierSlot> createState() => _DossierSlotState();
}

class _DossierSlotState extends State<DossierSlot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    value: widget.open ? 1 : 0,
  );
  late final Animation<double> _curve = CurvedAnimation(
    parent: _controller,
    curve: DelphosMotion.easeOut,
  );

  @override
  void initState() {
    super.initState();
    _controller.addStatusListener((status) {
      if (status == AnimationStatus.dismissed) widget.onExited?.call();
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _controller.duration = DelphosMotion.duration(context, DelphosMotion.panel);
  }

  @override
  void didUpdateWidget(DossierSlot oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.open == oldWidget.open) return;
    if (widget.open) {
      _controller.forward();
    } else if (_controller.isDismissed) {
      // Not during this build: the callback may notify listeners.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) widget.onExited?.call();
      });
    } else {
      _controller.reverse();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        if (!widget.open && _controller.isDismissed) {
          return const SizedBox.shrink();
        }
        final t = _curve.value;
        return Opacity(
          opacity: t,
          child: Transform.translate(
            offset: Offset(DossierSlot.slide * (1 - t), 0),
            child: child,
          ),
        );
      },
      child: Padding(
        padding: const EdgeInsets.only(left: 20),
        child: SizedBox(width: 440, child: widget.child),
      ),
    );
  }
}
