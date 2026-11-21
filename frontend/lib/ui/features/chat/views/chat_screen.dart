/// Conversational scouting module: where scouting reports live.
library;

import 'package:flutter/widgets.dart';
import 'package:provider/provider.dart';

import '../../../../domain/models/chat_turn.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/action_button.dart';
import '../../../core/widgets/state_panel.dart';
import '../view_models/chat_view_model.dart';
import 'chat_capabilities_dialog.dart';
import 'chat_composer.dart';
import 'chat_empty_state.dart';
import 'chat_header.dart';
import 'chat_sessions_panel.dart';
import 'chat_turn_card.dart';

/// Renders the `/chat` workspace with tool-step feedback and capability pop-up.
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  // Provided by the app, so the conversation outlives this screen.
  late final ChatViewModel _vm = context.read<ChatViewModel>();
  final TextEditingController _input = TextEditingController();
  final FocusNode _inputFocus = FocusNode(debugLabel: 'chat prompt input');
  final ScrollController _scroll = ScrollController();
  int _lastScrollKey = 0;

  @override
  void dispose() {
    // The menu is part of this screen: it never reopens by itself.
    _vm.sessions.close();
    _input.dispose();
    _inputFocus.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _scheduleScrollToBottom(List<ChatTurn> turns) {
    if (turns.isEmpty) {
      _lastScrollKey = 0;
      return;
    }
    final last = turns.last;
    final key = Object.hash(
      turns.length,
      last.steps.length,
      last.assistantMessage?.length,
      last.players.length,
      last.errorMessage?.length,
      last.isStreaming,
    );
    if (key == _lastScrollKey) return;
    _lastScrollKey = key;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scroll.hasClients) return;
      _scroll.jumpTo(_scroll.position.maxScrollExtent);
    });
  }

  void _submit([String? override]) {
    final text = (override ?? _input.text).trim();
    if (text.isEmpty || _vm.isBusy || _vm.isRestoring) return;
    if (override == null) _input.clear();
    _vm.sendMessage(text);
  }

  void _pickSample(String prompt) {
    _vm.closeCapabilities();
    _input.text = prompt;
    _input.selection = TextSelection.collapsed(offset: prompt.length);
    _inputFocus.requestFocus();
  }

  static Widget _compact(Widget child) => Center(
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 880),
      child: child,
    ),
  );

  /// The turns, or a note while a saved session loads or fails to load.
  Widget _body(List<ChatTurn> turns) {
    if (_vm.isRestoring) {
      return _compact(
        const StatePanel(
          title: 'Cargando la conversación…',
          text: 'Recuperando los mensajes guardados.',
        ),
      );
    }
    if (_vm.restoreFailed) {
      return _compact(
        StatePanel(
          title: 'No se pudo abrir la conversación',
          text: 'Inténtalo de nuevo o empieza una conversación nueva.',
          action: ActionButton(
            label: 'Reintentar',
            onPressed: _vm.retryRestore,
          ),
        ),
      );
    }
    if (turns.isEmpty) {
      return _compact(ChatEmptyState(onOpenCapabilities: _vm.openCapabilities));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      spacing: 20,
      children: [
        if (_vm.shownMessages case final shown?)
          Text(
            'Mostrando los últimos $shown mensajes',
            textAlign: TextAlign.center,
            style: DelphosText.ui(
              size: TypeScale.secondary,
              color: DelphosColors.ink3,
            ),
          ),
        for (final (i, turn) in turns.indexed)
          ChatTurnCard(
            turn: turn,
            onRetry: _vm.canRetry && i == turns.length - 1
                ? _vm.retryLastTurn
                : null,
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: Listenable.merge([_vm, _vm.sessions]),
      builder: (context, _) {
        final turns = _vm.turns;
        if (!_vm.isRestoring && !_vm.restoreFailed) {
          _scheduleScrollToBottom(turns);
        }
        return Stack(
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ChatHeader(
                  hasTurns: turns.isNotEmpty,
                  onOpenCapabilities: _vm.openCapabilities,
                  onOpenSessions: _vm.sessions.open,
                  onClear: _vm.clearConversation,
                ),
                Expanded(
                  child: Stack(
                    children: [
                      SingleChildScrollView(
                        controller: _scroll,
                        padding: const EdgeInsets.fromLTRB(24, 20, 24, 20),
                        child: Center(
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 1360),
                            child: _body(turns),
                          ),
                        ),
                      ),
                      if (_vm.sessions.isOpen) ...[
                        // A click outside the menu closes it.
                        Positioned.fill(
                          child: GestureDetector(
                            behavior: HitTestBehavior.translucent,
                            onTap: _vm.sessions.close,
                          ),
                        ),
                        Positioned(
                          top: 8,
                          right: 24,
                          child: ChatSessionsPanel(
                            vm: _vm.sessions,
                            activeSessionId: _vm.sessionId,
                            onPick: _vm.openSession,
                            onNew: _vm.clearConversation,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                ChatComposer(
                  controller: _input,
                  focusNode: _inputFocus,
                  enabled: !_vm.isBusy && !_vm.isRestoring,
                  onSend: _submit,
                ),
              ],
            ),
            if (_vm.isCapabilitiesOpen)
              ChatCapabilitiesDialog(
                onClose: _vm.closeCapabilities,
                onPickPrompt: _pickSample,
              ),
          ],
        );
      },
    );
  }
}
