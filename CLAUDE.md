# Aktüel Broşür

Türkiye'deki marketlerin aktüel broşürlerini gösteren Flutter uygulaması + veriyi toplayan
Python kazıyıcı (GitHub Actions'ta zamanlanmış çalışır). Kararların ve ilerlemenin tamamı
`PLAN.md` dosyasındadır; işe başlamadan önce onu oku.

## Roller

- **Ana oturum (yönetici):** kod yazmaz. Görev tanımlar, `worker` alt ajanına verir, çıktıyı
  denetler (farkı okur, testleri yeniden çalıştırır, emülatörde bakar), düzelttirir, kabul edince
  commit atar ve `PLAN.md` ilerleme günlüğünü günceller.
- **`worker` (Opus 5.5, high):** kodu yazar. Tanımı `.claude/agents/worker.md` içinde.

## Kurallar

- Bot engeli dolanılmaz: sahte tarayıcı parmak izi, vekil sunucu döndürme, CAPTCHA çözme,
  şifreli içerik çözme yazılmaz. Engelleyen market web görünümüne alınır ya da listeden çıkar.
- Kazıyıcı kendini dürüst bir `User-Agent` ile tanıtır, alan adı başına saniyede en fazla 1 istek atar.
- Repoya gizli bilgi girmez (API anahtarı, servis hesabı dosyası, `.env`). Gizli bilgiler GitHub Secrets'ta durur.
- Bir kaynak bozulursa diğerleri etkilenmez; şemaya uymayan çıktı yayınlanmaz.
- Kod, tanımlayıcılar ve commit mesajları İngilizce; arayüz metinleri Türkçe ve çeviri dosyasında.
- Arayüz yaşlı kullanıcıya göre: dokunma hedefi en az 56 dp, yazı en az 18 sp, yüksek kontrast.

## Komutlar

Kazıyıcı (proje kökünden çalıştırılır; `scraper/` Python paketidir, sanal ortam kökteki `.venv`):

```bash
python -m pytest
```

```bash
python -m scraper run --only bim --dry-run
```

Uygulama (`app/` içinde):

```bash
flutter analyze
```

```bash
flutter test
```

```bash
flutter run -d emulator-5554
```

Emülatör: `flutter emulators --launch Medium_Phone`
