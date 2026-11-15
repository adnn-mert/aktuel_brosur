/// Remembers whether the notification offer was already made, so it is made
/// at most once on its own ("never nag"). This is interface memory, not
/// catalog data; it lives here until the data layer offers a home for it
/// (see DESIGN.md, section 16).
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

abstract interface class NotificationOfferStore {
  /// True once the offer window was shown, or the user switched
  /// notifications on or off by hand.
  Future<bool> wasOffered();

  Future<void> markOffered();
}

/// [NotificationOfferStore] on top of `shared_preferences`.
class PrefsNotificationOfferStore implements NotificationOfferStore {
  PrefsNotificationOfferStore({Future<SharedPreferences> Function()? prefs})
    : _prefs = prefs ?? SharedPreferences.getInstance;

  static const String key = 'notification_offer_shown';

  final Future<SharedPreferences> Function() _prefs;

  @override
  Future<bool> wasOffered() async {
    try {
      return (await _prefs()).getBool(key) ?? false;
    } on Object {
      // When in doubt, do not ask: a missed offer costs less than a repeated one.
      return true;
    }
  }

  @override
  Future<void> markOffered() async {
    try {
      await (await _prefs()).setBool(key, true);
    } on Object {
      // Nothing to do; the worst case is one more offer later.
    }
  }
}

/// In-memory [NotificationOfferStore] for tests and previews.
class MemoryNotificationOfferStore implements NotificationOfferStore {
  MemoryNotificationOfferStore({this.offered = false});

  bool offered;

  @override
  Future<bool> wasOffered() async => offered;

  @override
  Future<void> markOffered() async => offered = true;
}

final notificationOfferStoreProvider = Provider<NotificationOfferStore>(
  (ref) => PrefsNotificationOfferStore(),
);
