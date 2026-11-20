// Rules of how SSE events build a turn's steps: a step starts running on
// `tool_start`, ends on the `tool` with its number, an older backend's bare
// `tool` still appends a finished step, and no step stays running once the
// turn ends.
import 'package:delphos_frontend/data/models/chat_sse_event.dart';
import 'package:delphos_frontend/domain/models/chat_tool_step.dart';
import 'package:delphos_frontend/domain/models/chat_turn.dart';
import 'package:delphos_frontend/ui/features/chat/view_models/chat_turn_events.dart';
import 'package:flutter_test/flutter_test.dart';

ChatTurn apply(ChatTurn turn, String event, Map<String, Object?> data) =>
    applyChatEvent(
      turn,
      ChatSseEvent(event: event, data: data),
      onSession: (_) {},
    );

const _turn = ChatTurn(userMessage: 'Busca delanteros', isStreaming: true);

void main() {
  test('tool_start adds a running step with the server description', () {
    final turn = apply(_turn, 'tool_start', {
      'step': 1,
      'tool': 'search_players',
      'description': 'Buscando delanteros infravalorados',
    });

    expect(turn.steps, hasLength(1));
    expect(turn.steps.single.state, ChatStepState.running);
    expect(turn.steps.single.id, 1);
    expect(turn.steps.single.stepTitle, 'Buscando delanteros infravalorados');
    expect(turn.steps.single.summary, isEmpty);
  });

  test('tool finishes the step with the same number in place', () {
    var turn = apply(_turn, 'tool_start', {
      'step': 1,
      'tool': 'search_players',
      'description': 'Buscando delanteros infravalorados',
    });
    turn = apply(turn, 'tool_start', {
      'step': 2,
      'tool': 'get_player_valuation',
      'description': 'Revisando la valoración de Harry Kane',
    });
    turn = apply(turn, 'tool', {
      'step': 1,
      'tool': 'search_players',
      'ok': true,
      'summary': 'Se encontraron 2 jugadores.',
      'description': 'Buscando delanteros infravalorados',
    });

    expect(turn.steps, hasLength(2));
    expect(turn.steps[0].state, ChatStepState.done);
    expect(turn.steps[0].summary, 'Se encontraron 2 jugadores.');
    expect(turn.steps[1].state, ChatStepState.running);
  });

  test('a failed tool marks its step as an error', () {
    var turn = apply(_turn, 'tool_start', {
      'step': 1,
      'tool': 'search_players',
      'description': 'Buscando delanteros',
    });
    turn = apply(turn, 'tool', {
      'step': 1,
      'tool': 'search_players',
      'ok': false,
      'summary': 'boom',
    });

    expect(turn.steps.single.isError, isTrue);
    expect(turn.steps.single.stepTitle, 'Buscando delanteros');
  });

  test('a bare tool event from an older backend appends a finished step', () {
    final turn = apply(_turn, 'tool', {
      'tool': 'search_players',
      'ok': true,
      'summary': 'Se consultaron 2 jugadores en el mercado.',
    });

    expect(turn.steps.single.state, ChatStepState.done);
    expect(turn.steps.single.stepTitle, 'Búsqueda de jugadores en el mercado');
    expect(
      turn.steps.single.summary,
      'Se consultaron 2 jugadores en el mercado.',
    );
  });

  test('a description that reads as code is replaced by the generic title', () {
    final turn = apply(_turn, 'tool_start', {
      'step': 1,
      'tool': 'search_players',
      'description': 'Ejecutando {"position": "Attack"}',
    });

    expect(turn.steps.single.stepTitle, 'Búsqueda de jugadores en el mercado');
  });

  test('a code-looking summary never reaches the step', () {
    final turn = apply(_turn, 'tool', {
      'step': 1,
      'tool': 'search_players',
      'ok': true,
      'summary': '{"total": 2}',
    });

    expect(turn.steps.single.summary, isNot(contains('{')));
    expect(turn.steps.single.summary, isNotEmpty);
  });

  test('message and error events settle steps that still run', () {
    final started = apply(_turn, 'tool_start', {
      'step': 1,
      'tool': 'search_players',
      'description': 'Buscando delanteros',
    });

    final answered = apply(started, 'message', {'message': 'Listo.'});
    expect(answered.steps.single.state, ChatStepState.done);
    expect(answered.isStreaming, isFalse);

    final failed = apply(started, 'error', {'detail': 'x'});
    expect(failed.steps.single.state, ChatStepState.failed);
    expect(failed.isStreaming, isFalse);
  });
}
