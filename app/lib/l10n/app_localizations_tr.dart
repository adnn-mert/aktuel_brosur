// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Turkish (`tr`).
class AppLocalizationsTr extends AppLocalizations {
  AppLocalizationsTr([String locale = 'tr']) : super(locale);

  @override
  String get appTitle => 'Aktüel Broşür';

  @override
  String get chainsTitle => 'Marketler';

  @override
  String get sectionCurrent => 'Bu hafta';

  @override
  String get sectionUpcoming => 'Gelecek hafta';

  @override
  String get sectionPast => 'Geçmiş';

  @override
  String get loading => 'Yükleniyor…';

  @override
  String get loadError =>
      'Broşürler yüklenemedi. İnternet bağlantınızı kontrol edin.';

  @override
  String get retry => 'Tekrar dene';

  @override
  String get staleNotice =>
      'İnternete bağlanılamadı. Son kaydedilen broşürler gösteriliyor.';

  @override
  String get noBrochures => 'Şu an gösterilecek broşür yok.';

  @override
  String get openChainWebsite => 'Marketin katalog sayfasını aç';

  @override
  String pageCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count sayfa',
      one: '1 sayfa',
    );
    return '$_temp0';
  }

  @override
  String get productsTitle => 'Ürünler';

  @override
  String get updateRequired =>
      'Bu broşürleri göstermek için uygulamanın yeni sürümü gerekiyor.';
}
