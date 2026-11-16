/// Lets a pop-up trigger take focus before the pop-up opens, so closing the
/// pop-up can return focus there even after a mouse click.
library;

import 'package:flutter/widgets.dart';

/// Wraps a trigger button; `builder` gets a callback that focuses it.
class ChatOpenerFocus extends StatefulWidget {
  const ChatOpenerFocus({super.key, required this.builder});

  /// Builds the trigger; call `focusOpener` before opening the pop-up.
  final Widget Function(BuildContext context, VoidCallback focusOpener) builder;

  @override
  State<ChatOpenerFocus> createState() => _ChatOpenerFocusState();
}

class _ChatOpenerFocusState extends State<ChatOpenerFocus> {
  final FocusNode _node = FocusNode(
    debugLabel: 'chat pop-up opener',
    canRequestFocus: false,
    skipTraversal: true,
  );

  @override
  void dispose() {
    _node.dispose();
    super.dispose();
  }

  void _focusOpener() {
    final trigger = _node.traversalDescendants.firstOrNull;
    trigger?.requestFocus();
  }

  @override
  Widget build(BuildContext context) =>
      Focus(focusNode: _node, child: widget.builder(context, _focusOpener));
}
