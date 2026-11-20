/// The "Conversaciones" menu (DESIGN.md §5, a floating layer): the saved
/// sessions, newest first, under a "Nueva conversación" action. It shows the
/// loading, empty and error states in place of the list, closes on Escape,
/// and returns focus to whatever had it when it opened.
library;

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

import '../../../../domain/models/chat_session_summary.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/theme/delphos_shadows.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/view_models/section_status.dart';
import '../../../core/widgets/action_button.dart';
import '../view_models/chat_sessions_view_model.dart';
import 'chat_hairline.dart';
import 'chat_session_row.dart';

/// The menu card; the screen places it under the header.
class ChatSessionsPanel extends StatefulWidget {
  const ChatSessionsPanel({
    super.key,
    required this.vm,
    required this.activeSessionId,
    required this.onPick,
    required this.onNew,
  });

  static const double width = 360;
  static const double maxListHeight = 340;

  final ChatSessionsViewModel vm;

  /// The session on show, drawn as selected.
  final String? activeSessionId;
  final ValueChanged<String> onPick;
  final VoidCallback onNew;

  @override
  State<ChatSessionsPanel> createState() => _ChatSessionsPanelState();
}

class _ChatSessionsPanelState extends State<ChatSessionsPanel> {
  final FocusNode _focus = FocusNode(debugLabel: 'chat sessions');

  /// What had focus when the menu opened; captured before focus moves in.
  final FocusNode? _opener = FocusManager.instance.primaryFocus;

  @override
  void initState() {
    super.initState();
    // Not `autofocus`: the opener already has focus, and autofocus never
    // takes it from the control that has it.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _focus.requestFocus();
    });
  }

  @override
  void dispose() {
    final opener = _opener;
    _focus.dispose();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // Only when focus is nowhere in particular: a control that took focus
      // meanwhile (a picked session's prompt input) keeps it.
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

  Widget _list(List<ChatSessionSummary> sessions) => ConstrainedBox(
    constraints: const BoxConstraints(
      maxHeight: ChatSessionsPanel.maxListHeight,
    ),
    child: SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final session in sessions)
            ChatSessionRow(
              session: session,
              isActive: session.id == widget.activeSessionId,
              onPressed: () => widget.onPick(session.id),
            ),
        ],
      ),
    ),
  );

  Widget _note(String text, {Widget? action}) {
    return Semantics(
      liveRegion: true,
      container: true,
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          spacing: 10,
          children: [
            Text(
              text,
              style: DelphosText.ui(
                size: TypeScale.secondary,
                color: DelphosColors.ink2,
              ),
            ),
            ?action,
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.escape): widget.vm.close,
      },
      child: Focus(
        focusNode: _focus,
        child: Semantics(
          explicitChildNodes: true,
          label: 'Conversaciones',
          child: Container(
            width: ChatSessionsPanel.width,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: DelphosColors.surface,
              borderRadius: BorderRadius.circular(DelphosRadius.card),
              border: Border.all(color: DelphosColors.rule),
              boxShadow: DelphosShadows.float,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              spacing: 10,
              children: [
                Row(
                  spacing: 12,
                  children: [
                    Expanded(
                      child: Text(
                        'Conversaciones',
                        style: DelphosText.ui(
                          size: TypeScale.section,
                          weight: FontWeight.w700,
                        ),
                      ),
                    ),
                    ActionButton(
                      label: 'Nueva conversación',
                      onPressed: widget.onNew,
                    ),
                  ],
                ),
                const ChatHairline(),
                ListenableBuilder(
                  listenable: widget.vm,
                  builder: (context, _) {
                    final load = widget.vm.sessions;
                    return switch (load.status) {
                      SectionStatus.ready when load.value!.isNotEmpty => _list(
                        load.value!,
                      ),
                      SectionStatus.ready || SectionStatus.absent => _note(
                        'Todavía no hay conversaciones guardadas.',
                      ),
                      SectionStatus.error => _note(
                        'No se pudieron cargar las conversaciones.',
                        action: ActionButton(
                          label: 'Reintentar',
                          onPressed: widget.vm.retry,
                        ),
                      ),
                      SectionStatus.loading => _note(
                        'Cargando conversaciones…',
                      ),
                    };
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
