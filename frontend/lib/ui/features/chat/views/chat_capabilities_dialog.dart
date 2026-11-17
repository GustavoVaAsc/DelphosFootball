/// Pop-up explaining what the conversational scouting assistant can do.
library;

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import 'chat_capabilities_card.dart';

/// Modal card: traps focus, focuses its close button, closes on Escape and
/// returns focus to whatever had it when it opened, unless focus has already
/// moved on (picking a sample prompt focuses the prompt input).
class ChatCapabilitiesDialog extends StatefulWidget {
  const ChatCapabilitiesDialog({
    super.key,
    required this.onClose,
    required this.onPickPrompt,
  });

  final VoidCallback onClose;
  final ValueChanged<String> onPickPrompt;

  @override
  State<ChatCapabilitiesDialog> createState() => _ChatCapabilitiesDialogState();
}

class _ChatCapabilitiesDialogState extends State<ChatCapabilitiesDialog> {
  final FocusNode _closeFocus = FocusNode(debugLabel: 'chat pop-up close');
  final FocusScopeNode _scope = FocusScopeNode(debugLabel: 'chat pop-up');

  /// What had focus when the pop-up opened; captured before focus moves in.
  final FocusNode? _opener = FocusManager.instance.primaryFocus;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _closeFocus.requestFocus();
    });
  }

  @override
  void dispose() {
    final opener = _opener;
    _closeFocus.dispose();
    _scope.dispose();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // Only when focus is nowhere in particular (the pop-up's own nodes are
      // gone): a control that took focus meanwhile keeps it.
      final primary = FocusManager.instance.primaryFocus;
      final nowhere = primary == null || primary is FocusScopeNode;
      if (nowhere &&
          opener != null &&
          opener.context != null &&
          opener.canRequestFocus) {
        opener.requestFocus();
      }
    });
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: CallbackShortcuts(
        bindings: {
          const SingleActivator(LogicalKeyboardKey.escape): widget.onClose,
        },
        child: FocusScope(
          node: _scope,
          child: Semantics(
            scopesRoute: true,
            explicitChildNodes: true,
            label: 'Ventana de capacidades de PitIA',
            child: Container(
              color: DelphosColors.scrim,
              alignment: Alignment.center,
              padding: const EdgeInsets.all(24),
              child: ChatCapabilitiesCard(
                onClose: widget.onClose,
                onPickPrompt: widget.onPickPrompt,
                closeFocus: _closeFocus,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
