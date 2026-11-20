/// One saved conversation in the "Conversaciones" menu: its title over its
/// date. The conversation on show has the selected-row ground.
library;

import 'package:flutter/widgets.dart';

import '../../../../domain/models/chat_session_summary.dart';
import '../../../core/format/format.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/pressable.dart';

/// A pressable row that opens its session.
class ChatSessionRow extends StatelessWidget {
  const ChatSessionRow({
    super.key,
    required this.session,
    required this.isActive,
    required this.onPressed,
  });

  /// What a session without a title is called.
  static const String untitled = 'Conversación sin título';

  final ChatSessionSummary session;
  final bool isActive;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final title = switch (session.title?.trim()) {
      final text? when text.isNotEmpty => text,
      _ => untitled,
    };
    return Pressable(
      onPressed: onPressed,
      semanticLabel: 'Abrir conversación: $title',
      selected: isActive,
      borderRadius: DelphosRadius.segment,
      pressedScale: 1,
      builder: (context, hovered) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: isActive
              ? DelphosColors.selectedBg
              : (hovered ? DelphosColors.surfaceSubtle : null),
          borderRadius: BorderRadius.circular(DelphosRadius.segment),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          spacing: 2,
          children: [
            Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: DelphosText.ui(weight: FontWeight.w600),
            ),
            Text(
              formatSessionDate(session.updatedAt, now: DateTime.now()),
              style: DelphosText.ui(
                size: TypeScale.secondary,
                color: DelphosColors.ink3,
                tabular: true,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
