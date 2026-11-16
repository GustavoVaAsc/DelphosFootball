/// Conversational scouting module: where scouting reports live.
library;

import 'package:flutter/widgets.dart';
import 'package:provider/provider.dart';

import '../../../../data/repositories/chat_repository.dart';
import '../view_models/chat_view_model.dart';
import 'chat_capabilities_dialog.dart';
import 'chat_composer.dart';
import 'chat_empty_state.dart';
import 'chat_header.dart';
import 'chat_turn_card.dart';

/// Renders the `/chat` workspace with tool-step feedback and capability pop-up.
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  late final ChatViewModel _vm = ChatViewModel(
    repository: context.read<ChatRepository>(),
  );
  final TextEditingController _input = TextEditingController();
  final FocusNode _inputFocus = FocusNode(debugLabel: 'chat prompt input');

  @override
  void dispose() {
    _input.dispose();
    _inputFocus.dispose();
    _vm.dispose();
    super.dispose();
  }

  void _submit([String? override]) {
    final text = (override ?? _input.text).trim();
    if (text.isEmpty || _vm.isBusy) return;
    if (override == null) _input.clear();
    _vm.sendMessage(text);
  }

  void _pickSample(String prompt) {
    _vm.closeCapabilities();
    _input.text = prompt;
    _input.selection = TextSelection.collapsed(offset: prompt.length);
    _inputFocus.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _vm,
      builder: (context, _) {
        final turns = _vm.turns;
        return Stack(
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ChatHeader(
                  hasTurns: turns.isNotEmpty,
                  onOpenCapabilities: _vm.openCapabilities,
                  onClear: _vm.clearConversation,
                ),
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(24, 20, 24, 20),
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 880),
                        child: turns.isEmpty
                            ? ChatEmptyState(
                                onOpenCapabilities: _vm.openCapabilities,
                              )
                            : Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                spacing: 14,
                                children: [
                                  for (final (i, turn) in turns.indexed)
                                    ChatTurnCard(
                                      turn: turn,
                                      onRetry:
                                          _vm.canRetry && i == turns.length - 1
                                          ? _vm.retryLastTurn
                                          : null,
                                    ),
                                ],
                              ),
                      ),
                    ),
                  ),
                ),
                ChatComposer(
                  controller: _input,
                  focusNode: _inputFocus,
                  enabled: !_vm.isBusy,
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
