// The step trail while a turn streams: the active label shimmers, finished
// steps are static, and nothing shimmers once the turn is over.
import 'package:delphos_frontend/domain/models/chat_tool_step.dart';
import 'package:delphos_frontend/ui/core/widgets/shimmer_text.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_step_trail.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

Widget host({
  required List<ChatToolStep> steps,
  required bool isStreaming,
  bool reduced = false,
}) => MediaQuery(
  data: MediaQueryData(disableAnimations: reduced),
  child: Directionality(
    textDirection: TextDirection.ltr,
    child: ChatStepTrail(steps: steps, isStreaming: isStreaming),
  ),
);

const _running = ChatToolStep(
  id: 2,
  stepTitle: 'Revisando la valoración de Harry Kane',
  summary: '',
  state: ChatStepState.running,
);
const _done = ChatToolStep(
  id: 1,
  stepTitle: 'Buscando delanteros infravalorados',
  summary: 'Se encontraron 2 jugadores.',
);

Finder shimmering(String text) =>
    find.widgetWithText(ShimmerText, text, skipOffstage: false);

void main() {
  testWidgets('shimmers the first label before any step arrives', (
    tester,
  ) async {
    await tester.pumpWidget(host(steps: const [], isStreaming: true));

    expect(shimmering('Analizando tu petición…'), findsOneWidget);
  });

  testWidgets('shimmers the running step, not the finished one', (
    tester,
  ) async {
    await tester.pumpWidget(host(steps: [_done, _running], isStreaming: true));

    expect(shimmering(_running.stepTitle), findsOneWidget);
    expect(find.text(_done.stepTitle), findsOneWidget);
    expect(find.text(_done.summary), findsOneWidget);
    expect(find.byType(ShimmerText), findsOneWidget);
  });

  testWidgets('shimmers the wait after the last result', (tester) async {
    await tester.pumpWidget(host(steps: [_done], isStreaming: true));

    expect(shimmering('Analizando los resultados…'), findsOneWidget);
    expect(find.byType(ShimmerText), findsOneWidget);
  });

  testWidgets('nothing shimmers once the turn is over', (tester) async {
    await tester.pumpWidget(host(steps: [_done], isStreaming: true));
    expect(tester.hasRunningAnimations, isTrue);

    await tester.pumpWidget(host(steps: [_done], isStreaming: false));

    expect(find.byType(ShimmerText), findsNothing);
    expect(tester.hasRunningAnimations, isFalse);
    expect(
      find.text('Pasos realizados sobre la base del modelo'),
      findsOneWidget,
    );
  });

  testWidgets('a failed step reads "No se pudo completar"', (tester) async {
    const failed = ChatToolStep(
      id: 1,
      stepTitle: 'Buscando delanteros',
      summary: 'boom',
      state: ChatStepState.failed,
    );
    await tester.pumpWidget(host(steps: [failed], isStreaming: false));

    expect(find.text('No se pudo completar'), findsOneWidget);
    expect(find.text('boom'), findsNothing);
  });
}
