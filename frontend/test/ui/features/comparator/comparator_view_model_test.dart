// Tests for ComparatorViewModel: the reference's three requests, then each
// candidate's profile in parallel; a failing candidate stays a gap in its
// column; a replacements 404 is absent; a reference failure is the error
// state; a late answer for an earlier player is dropped.
import 'dart:async';

import 'package:delphos_frontend/data/repositories/player_repository.dart';
import 'package:delphos_frontend/ui/core/view_models/section_status.dart';
import 'package:delphos_frontend/ui/features/comparator/view_models/comparator_status.dart';
import 'package:delphos_frontend/ui/features/comparator/view_models/comparator_view_model.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import '../../../support/dossier_fixtures.dart';
import '../../../support/http_fakes.dart';

void main() {
  late List<String> requested;
  late Map<String, Completer<void>> gates;
  late Set<String> failing;
  late Set<String> missing;
  late ComparatorViewModel vm;

  setUp(() {
    requested = [];
    gates = {};
    failing = {};
    missing = {};
    final api = fakeApi((request) async {
      final path = request.url.path;
      requested.add(path);
      await gates[path]?.future;
      if (failing.contains(path)) {
        throw http.ClientException('offline', request.url);
      }
      if (missing.contains(path)) {
        return problemResponse(404, 'Not Found', 'none');
      }
      return jsonResponse(dossierJsonFor(path));
    });
    vm = ComparatorViewModel(players: PlayerRepository(apiClient: api));
  });
  tearDown(() => vm.dispose());

  Future<void> settle() async {
    for (var i = 0; i < 8; i++) {
      await Future<void>.delayed(Duration.zero);
    }
  }

  test('no player is the idle state and requests nothing', () {
    vm.show(null);
    expect(vm.status, ComparatorStatus.idle);
    expect(requested, isEmpty);
  });

  test('loads the reference, then every candidate in parallel', () async {
    gates['/players/72'] = Completer<void>();
    vm.show(7);
    expect(vm.status, ComparatorStatus.loading);
    await settle();
    expect(requested.take(3).toSet(), {
      '/players/7',
      '/players/7/valuation',
      '/players/7/replacements',
    });
    expect(requested.skip(3).toSet(), {
      '/players/71',
      '/players/72',
      '/players/73',
    });
    expect(vm.status, ComparatorStatus.ready);
    expect(vm.candidate(71).status, SectionStatus.ready);
    expect(vm.candidate(72).status, SectionStatus.loading);
    gates['/players/72']!.complete();
    await settle();
    expect(vm.candidate(72).value!.id, 72);
  });

  test('a failing candidate is an error in its column only', () async {
    failing.add('/players/72');
    vm.show(7);
    await settle();
    expect(vm.status, ComparatorStatus.ready);
    expect(vm.candidate(72).status, SectionStatus.error);
    expect(vm.candidate(73).status, SectionStatus.ready);
  });

  test('a replacements 404 is absent and the table still shows', () async {
    missing.add('/players/7/replacements');
    vm.show(7);
    await settle();
    expect(vm.status, ComparatorStatus.ready);
    expect(vm.replacements.status, SectionStatus.absent);
  });

  test('a failing reference is the error state, and retry recovers', () async {
    failing.add('/players/7/valuation');
    vm.show(7);
    await settle();
    expect(vm.status, ComparatorStatus.error);
    failing.clear();
    await vm.retry();
    await settle();
    expect(vm.status, ComparatorStatus.ready);
  });

  test('an earlier player answering late is dropped', () async {
    gates['/players/7'] = Completer<void>();
    vm.show(7);
    vm.show(8);
    await settle();
    gates['/players/7']!.complete();
    await settle();
    expect(vm.playerId, 8);
    expect(vm.reference.value!.id, 8);
  });
}
