/// User prompt bubble, aligned to the right of the scouting chat feed.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';

/// Displays the user's question in a compact navy chat bubble.
class ChatUserBubble extends StatelessWidget {
  const ChatUserBubble({super.key, required this.message});

  final String message;

  static const double _maxWidth = 680;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerRight,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: _maxWidth),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: DelphosColors.ink,
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(DelphosRadius.card),
              topRight: Radius.circular(DelphosRadius.card),
              bottomLeft: Radius.circular(DelphosRadius.card),
              bottomRight: Radius.circular(DelphosRadius.small),
            ),
          ),
          child: Text(
            message,
            style: DelphosText.ui(
              size: TypeScale.body,
              weight: FontWeight.w500,
              color: DelphosColors.onSidebar,
              height: 1.45,
            ),
          ),
        ),
      ),
    );
  }
}
