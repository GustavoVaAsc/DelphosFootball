/// A one-time fade for content that replaces a placeholder (DESIGN.md §5):
/// opacity 0 to 1 over 160 ms when the child first appears, so a dossier
/// section's data does not pop in over its skeleton. Opacity only, no
/// movement and no stagger; instant under reduced motion.
library;

import 'package:flutter/widgets.dart';

import '../theme/motion.dart';

/// Fades [child] in once, when this widget is first built.
class FadeInOnce extends StatefulWidget {
  const FadeInOnce({super.key, required this.child});

  final Widget child;

  @override
  State<FadeInOnce> createState() => _FadeInOnceState();
}

class _FadeInOnceState extends State<FadeInOnce>
    with SingleTickerProviderStateMixin {
  late final AnimationController _fade = AnimationController(vsync: this);
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    _fade.duration = DelphosMotion.duration(context, DelphosMotion.hover);
    _fade.forward();
  }

  @override
  void dispose() {
    _fade.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FadeTransition(
    opacity: CurvedAnimation(parent: _fade, curve: DelphosMotion.easeOut),
    child: widget.child,
  );
}
