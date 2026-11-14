/// Conversational scouting module replacing the static dossier reports.
library;

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:provider/provider.dart';

import '../../../../data/repositories/chat_repository.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/action_button.dart';
import '../view_models/chat_view_model.dart';
import 'chat_capabilities_dialog.dart';
import 'chat_composer.dart';
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
  void initState() {
    super.initState();
    HardwareKeyboard.instance.addHandler(_onKey);
  }

  @override
  void dispose() {
    HardwareKeyboard.instance.removeHandler(_onKey);
    _input.dispose();
    _inputFocus.dispose();
    _vm.dispose();
    super.dispose();
  }

  bool _onKey(KeyEvent event) {
    if (event is KeyDownEvent &&
        event.logicalKey == LogicalKeyboardKey.escape &&
        _vm.isCapabilitiesOpen) {
      _vm.closeCapabilities();
      return true;
    }
    return false;
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
                            ? _EmptyState(
                                onOpenCapabilities: _vm.openCapabilities,
                              )
                            : Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                spacing: 14,
                                children: [
                                  for (final turn in turns)
                                    ChatTurnCard(turn: turn),
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

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.onOpenCapabilities});

  final VoidCallback onOpenCapabilities;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: DelphosColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: DelphosColors.rule),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        spacing: 10,
        children: [
          Text(
            'Conversa con los datos calculados por el modelo',
            style: DelphosText.ui(
              size: TypeScale.section,
              weight: FontWeight.w600,
            ),
          ),
          Text(
            'Pregunta por jugadores concretos, solicita comparaciones frente a sus reemplazos o filtra oportunidades infravaloradas en lenguaje natural. Verás en todo momento qué consultas realiza el asistente antes de responder.',
            style: DelphosText.ui(color: DelphosColors.ink2, height: 1.5),
          ),
          ActionButton(
            label: 'Ver guía de capacidades y ejemplos',
            onPressed: onOpenCapabilities,
          ),
        ],
      ),
    );
  }
}
