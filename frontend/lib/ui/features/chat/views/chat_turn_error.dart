/// The failure of a turn: a fixed plain sentence and a retry button.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/widgets/action_button.dart';

/// Shows [message] in ink-2, with "Reintentar" when [onRetry] is given.
class ChatTurnError extends StatelessWidget {
  const ChatTurnError({super.key, required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 10,
      children: [
        Text(
          message,
          style: DelphosText.ui(color: DelphosColors.ink2, height: 1.45),
        ),
        if (onRetry != null)
          ActionButton(label: 'Reintentar', onPressed: onRetry),
      ],
    );
  }
}
