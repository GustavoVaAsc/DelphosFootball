/// Message composer at the bottom of the conversational scouting view.
library;

import 'package:material_ui/material_ui.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/widgets/action_button.dart';
import '../../../core/widgets/focus_ring.dart';
import '../../../core/widgets/focus_visibility.dart';

/// Text input and send button bounded to a single scouting request at a time.
class ChatComposer extends StatelessWidget {
  const ChatComposer({
    super.key,
    required this.controller,
    required this.focusNode,
    required this.enabled,
    required this.onSend,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final bool enabled;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final style = DelphosText.ui();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
      decoration: const BoxDecoration(
        color: DelphosColors.surface,
        border: Border(top: BorderSide(color: DelphosColors.rule)),
      ),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 880),
          child: Row(
            spacing: 12,
            children: [
              Expanded(
                child: ListenableBuilder(
                  listenable: Listenable.merge([
                    focusNode,
                    FocusVisibility.keyboard,
                  ]),
                  builder: (context, child) => FocusRing(
                    visible:
                        focusNode.hasFocus && FocusVisibility.keyboard.value,
                    borderRadius: 8,
                    child: child!,
                  ),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 10,
                    ),
                    decoration: BoxDecoration(
                      color: DelphosColors.surfaceSubtle,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: DelphosColors.controlBorder),
                    ),
                    child: TextField(
                      controller: controller,
                      focusNode: focusNode,
                      enabled: enabled,
                      minLines: 1,
                      maxLines: 4,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => enabled ? onSend() : null,
                      style: style,
                      cursorColor: DelphosColors.ink,
                      decoration: InputDecoration.collapsed(
                        hintText: 'Escribe una consulta o comparación (p. ej. Compara a Harry Kane con sus reemplazos)…',
                        hintStyle: style.copyWith(color: DelphosColors.ink3),
                      ),
                    ),
                  ),
                ),
              ),
              ActionButton(
                label: 'Enviar',
                primary: true,
                onPressed: enabled ? onSend : null,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
