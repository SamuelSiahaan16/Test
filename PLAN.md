# Rencana yt-views-bot — Python GUI

## 1. Tujuan

Membuat aplikasi desktop Python untuk menjalankan sesi pemutaran video YouTube secara otomatis melalui Chromium yang dikendalikan Playwright. Pengguna dapat mengatur URL video, target sesi, jumlah browser yang berjalan bersamaan, serta durasi menonton dalam detik.

**Catatan pengukuran:** label `Target Views` di GUI adalah target jumlah sesi pemutaran yang dijalankan aplikasi. Sesi selesai tidak menjamin penambahan view pada YouTube. Aplikasi memisahkan bukti pemutaran dari perubahan counter view publik. Kenaikan counter dapat diamati, tetapi tidak dapat dipastikan berasal dari sesi aplikasi.

## 2. Fitur MVP

| Komponen | Fungsi |
| --- | --- |
| Link YouTube | Input URL satu video yang akan diputar. |
| Target Views / Sesi | Jumlah sesi pemutaran yang ingin diselesaikan. |
| Maksimal Jendela Chromium | Batas jendela browser yang terbuka bersamaan; setiap jendela berisi satu tab video. |
| Durasi Tonton (detik) | Lama video benar-benar diputar pada setiap sesi. |
| Run | Memvalidasi input lalu menjalankan antrean sesi. |
| Stop | Membatalkan antrean dan menghentikan sesi aktif. |
| Progress | Menampilkan sesi selesai, gagal, dibatalkan, aktif, dan tersisa. |
| Kesehatan Pemutaran | Menampilkan video yang terdeteksi, player aktif, buffering, dan error per sesi. |
| Pantau Views Publik | Membaca angka pada halaman YouTube melalui Playwright sebelum run, setiap 120 detik, dan setelah run. Tanpa YouTube Data API/API key. |
| Ringkasan Views | Menampilkan counter awal, pembacaan terakhir, selisih, status, dan waktu pengecekan. |
| Cek Views Sekarang | Membaca ulang halaman setelah run melalui jendela monitor sementara, tanpa menambahkan sesi pemutaran ke target. |
| Pembersihan Data Sesi | Context sementara per sesi; ditutup dan dibuang setelah selesai, gagal, atau Stop. |
| Log GUI | Menampilkan aktivitas aplikasi secara langsung. |
| Log Lokal | Menyimpan log setiap run ke folder `log/`. |

Chromium adalah browser yang dibuka, sedangkan Playwright adalah library untuk mengendalikannya. Pada MVP, satu worker mengelola satu browser dengan satu jendela dan satu tab video, lalu menjalankan satu sesi pada satu waktu. Batas ini menghitung jendela, bukan proses OS internal Chromium yang dapat berjumlah lebih banyak.

## 3. Teknologi

- **Python 3.11+** sebagai bahasa utama.
- **PySide6** untuk GUI desktop, signal/slot, dan worker thread.
- **Playwright Python dengan API async** untuk membuka Chromium dan mengendalikan video.
- **asyncio** untuk antrean, pembatasan konkurensi, dan pembatalan tugas.
- **logging** bawaan Python untuk log file dan tampilan GUI.
- **unittest** untuk pengujian logika, Chromium lokal, dan lifecycle GUI.

Versi dependency ditetapkan saat implementasi setelah kompatibilitasnya diperiksa.

## 4. Rancangan GUI

```text
+------------------------------------------------------------+
| yt-views-bot                                               |
|                                                            |
| Link YouTube             [ https://www.youtube.com/...    ] |
| Target Views / Sesi      [ 10                            ] |
| Maksimal Jendela Chromium [ 2                            ] |
| Durasi Tonton (detik)    [ 30                            ] |
| [x] Pantau views publik via halaman — setiap 120 detik      |
|                                                            |
| [ Run ]  [ Stop ]                                          |
|                                                            |
| Status: Berjalan                                          |
| Selesai: 3/10 | Aktif: 2 | Gagal: 0 | Dibatalkan: 0          |
| [====================                              ]       |
| Pemutaran: 2 aktif | Buffering: 0 | Error: 0                |
| Views awal: -- | Terakhir: -- | Selisih: --                 |
| Status views: Belum diperiksa | Dicek: --                   |
| [ Cek Views Sekarang ]                                     |
|                                                            |
| Log                                                        |
| 14:00:01 INFO  Run dimulai                                 |
| 14:00:02 INFO  Worker 1 membuka video                       |
| 14:00:05 INFO  Sesi 1 mulai memutar video                   |
| 14:00:35 INFO  Sesi 1 selesai                              |
+------------------------------------------------------------+
```

Perilaku GUI:

- Saat idle, tombol Run aktif dan Stop nonaktif.
- Saat berjalan, input dikunci, Run nonaktif, dan Stop aktif.
- Setelah Stop ditekan, status berubah menjadi `Menghentikan...` sampai browser selesai ditutup.
- Setelah run berakhir, input dan tombol Run kembali aktif.
- Log otomatis bergulir ke baris terbaru, dengan batas baris di GUI agar penggunaan memori tetap terkendali.
- Log yang dikeluarkan aplikasi disimpan lengkap ke file meskipun baris lama sudah dilepas dari GUI.
- Status pemutaran dan status views ditampilkan terpisah. Jangan menggunakan label `view diterima` atau `bot terbukti berhasil` berdasarkan counter publik.
- Tombol Cek Views Sekarang aktif ketika idle dan tidak ada pengecekan yang berjalan. Tombol ini membuka jendela monitor sementara tanpa sengaja memulai pemutaran; tidak menambah target sesi.

## 5. Validasi Input

- URL wajib menggunakan HTTPS dan host YouTube yang didukung, misalnya `youtube.com`, `www.youtube.com`, atau `youtu.be`.
- Host diperiksa melalui parser URL, bukan pencocokan potongan teks.
- MVP mendukung satu video melalui URL `watch?v=...`, `youtu.be/...`, dan `shorts/VIDEO_ID`. URL Shorts dibuka pada halaman Shorts asli; monitor views menggunakan halaman watch; playlist dan live stream belum didukung.
- Target sesi, batas browser, dan durasi harus berupa bilangan bulat positif.
- Batas browser efektif adalah nilai terkecil antara batas yang diisi pengguna dan jumlah target sesi.
- Nilai awal yang disarankan untuk pengujian: target 1 sesi, maksimal 1 browser, durasi 30 detik.
- Jika folder log tidak dapat dibuat atau ditulis, aplikasi menampilkan error sebelum memulai browser.
- Fitur pemantauan statistik bersifat opsional dan tidak membutuhkan API key. Jika halaman tidak menyediakan angka yang dapat dibaca, tampilkan alasannya; sesi pemutaran tetap dapat berjalan.

## 6. Arsitektur

```text
GUI PySide6 — main thread
    |
    | konfigurasi, perintah Run / Stop
    v
Runner — QThread dengan event loop asyncio
    |
    +-- Antrean sesi
    +-- Worker 1 --> Chromium 1
    +-- Worker 2 --> Chromium 2
    +-- Worker N --> Chromium N
    +-- ViewCountMonitor --> Halaman YouTube via Playwright
    +-- Batas jendela bersama untuk worker dan monitor
    |
    +-- Signal progress dan status --> GUI
    +-- Logging --> file + signal log GUI
```

Aturan implementasi:

- Main thread hanya mengurus GUI supaya aplikasi tetap responsif.
- Playwright dan seluruh objek browser dibuat, dipakai, dan ditutup di event loop runner yang sama.
- Worker tidak memperbarui widget secara langsung; perubahan GUI dikirim lewat signal Qt.
- Perintah Stop dikirim ke event loop runner secara thread-safe.
- Jumlah worker membatasi browser aktif; browser ditutup sebelum worker membuat penggantinya.
- Setiap sesi memiliki ID dan status akhir yang jelas: selesai, gagal, atau dibatalkan.
- Monitor statistik memakai jendela sementara tersendiri dalam event loop runner, dengan batas jendela bersama worker. Semua hasil terikat pada run ID dan video ID agar hasil lama tidak menimpa run baru. Detail pembagian slot ada di bagian 16.

## 7. Alur Run

1. Pengguna mengisi form lalu menekan Run.
2. Aplikasi memvalidasi konfigurasi dan kesiapan folder log.
3. Aplikasi membuat run ID dan file log, lalu mengunci input.
4. Runner membuat antrean sesuai target sesi dan memulai worker sesuai batas browser.
5. Setiap worker membuka Chromium dalam mode terlihat, lalu membuka URL video.
6. Worker menunggu player siap dan mencoba memulai pemutaran.
7. Worker memantau pertambahan posisi video. Waktu buffering dan pause tidak dihitung sebagai waktu menonton.
8. Sesi dinyatakan selesai setelah akumulasi waktu pemutaran mencapai durasi yang diminta.
9. Context sementara ditutup, browser ditutup, dan file sementara milik sesi dibersihkan melalui blok `finally` sesuai bagian 17, kemudian worker mengambil sesi berikutnya.
10. Saat seluruh sesi memiliki hasil akhir, runner menutup Playwright dan mengirim ringkasan ke GUI serta log.

Jika pemantauan views aktif, ambil baseline sebelum sesi pertama, jadwalkan pengecekan setiap 120 detik selama run, lalu satu pembacaan setelah run selesai secara normal. Setiap pembacaan memiliki timeout 30 detik setelah memperoleh slot jendela dan berjalan di luar main thread. Jika seluruh slot sedang digunakan, pengecekan menunggu slot berikutnya tanpa mengganggu pemutaran aktif. Jika baseline gagal, jangan mengambil pembacaan tengah run sebagai baseline awal; selisih terhadap awal tetap `tidak diketahui`.

MVP memakai jumlah sesi tetap: sesi gagal dicatat sebagai gagal dan tidak otomatis diganti. Dengan demikian, target 10 menghasilkan total 10 hasil akhir, bukan percobaan tanpa batas sampai memperoleh 10 keberhasilan.

Untuk URL Shorts, target efektif dibatasi panjang video yang valid. Sesi dapat selesai di akhir video jika pemutaran terverifikasi mendekati target dengan toleransi sampling maksimal 0,75 detik (maksimal 10% target). Untuk URL lainnya, durasi yang diminta tetap berlaku. Akhir video tanpa durasi terverifikasi yang cukup tetap gagal; tidak ada pengulangan otomatis.

## 8. Alur Stop dan Tutup Aplikasi

1. Tombol Stop mengirim permintaan pembatalan ke runner.
2. Worker berhenti mengambil sesi baru.
3. Tugas sesi aktif dibatalkan dan menjalankan pembersihan browser.
4. Sesi yang belum selesai ditandai dibatalkan tepat satu kali.
5. Runner menutup seluruh browser dan Playwright dengan batas waktu pembersihan.
6. Ringkasan akhir ditulis ke log sebelum GUI kembali ke keadaan idle.

Jika pengguna menutup jendela saat run aktif, aplikasi menjalankan alur Stop terlebih dahulu. Hindari menghentikan thread secara paksa atau menutup proses Chrome milik pengguna lain.

Stop juga membatalkan jadwal dan pembacaan statistik aktif, lalu membersihkan jendela monitor. Jangan menambahkan masa tunggu statistik setelah Stop. Pertahankan hasil pembacaan terakhir beserta waktunya; pembacaan ulang dapat dilakukan lewat Cek Views Sekarang setelah aplikasi idle.

## 9. Penanganan Error

| Kondisi | Perilaku |
| --- | --- |
| URL atau angka tidak valid | Tampilkan pesan dekat input; run tidak dimulai. |
| Chromium Playwright belum terpasang | Tampilkan instruksi pemasangan browser. |
| Navigasi atau player timeout | Tandai sesi gagal, tutup browser, lanjutkan antrean. |
| Video privat, dihapus, atau dibatasi | Catat alasan kegagalan yang terdeteksi. |
| Pemutaran tidak mulai atau buffering berkepanjangan | Akhiri sesi melalui timeout yang terukur. |
| Halaman membutuhkan login atau tindakan manual | Catat sesi sebagai terhalang; tidak melewati pembatasan. |
| Browser crash | Catat sesi gagal; worker dapat melanjutkan dengan browser baru. |
| Penulisan log gagal saat berjalan | Tampilkan error, hentikan run secara terkendali, lalu bersihkan browser. |
| Elemen views berubah, halaman dibatasi, atau angka ambigu | Tampilkan status monitor yang spesifik; jangan menebak nilai. Sesi pemutaran tetap berjalan. |
| Pembacaan halaman timeout / koneksi putus | Tandai pembacaan gagal; pertahankan angka terakhir dan tandai sebagai data lama. |

Setiap operasi yang berpotensi menunggu memiliki timeout: membuka halaman, menunggu player, menunggu pemutaran, dan menutup browser. Batas waktu total sesi juga diperlukan supaya sesi tidak menggantung selamanya.

## 10. Logging Lokal

Lokasi log adalah folder `log/` di direktori proyek saat dijalankan dari source. Jika nanti dikemas menjadi aplikasi, gunakan direktori data aplikasi pengguna yang dapat ditulis, dengan subfolder `log/`. Path absolut log aktif ditampilkan di GUI.

```text
log/
  run_20261110_140001_a1b2c3.log
  run_20261110_153045_d4e5f6.log
```

Format log:

```text
2026-11-10 14:00:01+07:00 INFO run=a1b2c3 event=run_started target=10 concurrency=2 duration_seconds=30
2026-11-10 14:00:05+07:00 INFO run=a1b2c3 worker=1 session=1 event=playback_started
2026-11-10 14:00:35+07:00 INFO run=a1b2c3 worker=1 session=1 event=session_completed played_seconds=30
2026-11-10 14:03:00+07:00 INFO run=a1b2c3 event=run_finished completed=9 failed=1 cancelled=0
```

Informasi yang dicatat:

- Waktu dengan zona waktu, level log, run ID, worker ID, dan session ID.
- Konfigurasi run dan video ID yang diperlukan untuk diagnosis.
- Perubahan status, durasi pemutaran, timeout, dan alasan kegagalan.
- Traceback error teknis di file, dengan pesan ringkas di GUI.
- Ringkasan hasil akhir dan lama run.
- Hasil pemeriksaan player, buffering, identitas video, dan error media.
- Snapshot statistik: sumber `youtube_page`, video ID, waktu jadwal dan pembacaan aktual, teks asli, locale, presisi (`exact`, `abbreviated`, `unavailable`), counter persis jika tersedia, selisih bertanda jika valid, serta status pemantauan. Kegagalan baca tidak dicatat sebagai angka nol.

Jangan mencatat cookie, token, atau informasi login. MVP membuat satu file per run tanpa penghapusan otomatis; retensi log dapat ditambahkan kemudian.

## 11. Struktur Proyek

```text
yt-views/
  main.py
  requirements.txt
  README.md
  PLAN.md
  .gitignore
  app/
    __init__.py
    config.py
    gui/
      __init__.py
      main_window.py
    core/
      __init__.py
      runner.py
      browser_worker.py
      models.py
      playback_probe.py
      view_count_monitor.py
    utils/
      __init__.py
      logging_setup.py
      validators.py
  tests/
    test_validators.py
    test_runner.py
    test_playback_probe.py
    test_view_count_monitor.py
  log/
    .gitkeep
```

File `log/*.log`, `.venv/`, dan cache Python dimasukkan ke `.gitignore`.

## 12. Tahapan Implementasi

### Tahap 1 — Fondasi dan GUI

- Membuat virtual environment dan memasang dependency.
- Membuat form, tombol Run/Stop, indikator progress, dan panel log.
- Menerapkan validasi konfigurasi dan state GUI.

**Hasil:** GUI dapat menerima konfigurasi dan menampilkan kesalahan input.

### Tahap 2 — Logging dan Runner Simulasi

- Membuat log file per run dan meneruskan log ke GUI.
- Membuat worker simulasi tanpa akses YouTube.
- Menguji antrean, batas worker, progress, dan pembatalan.

**Hasil:** alur Run/Stop dan konkurensi dapat diverifikasi tanpa membuka browser.

### Tahap 3 — Integrasi Playwright

- Memasang Chromium Playwright.
- Membuka satu video, mendeteksi pemutaran, dan mengukur durasi yang benar-benar diputar.
- Menambahkan timeout, hasil sesi, dan pembersihan browser.
- Mengintegrasikan worker browser dengan antrean yang sudah diuji.
- Menambahkan pemeriksaan identitas video, status player, dan klasifikasi buffering/error sesuai bagian 16.
- Menambahkan monitor counter publik opsional, baseline, polling, pembacaan akhir, dan tombol Cek Views Sekarang.

**Hasil:** sesi pemutaran berjalan sesuai konfigurasi dengan batas browser yang ditaati.

### Tahap 4 — Pengujian dan Dokumentasi

- Memastikan Stop bekerja saat navigasi, menunggu player, dan pemutaran.
- Menguji error dan pembersihan browser.
- Menulis README untuk instalasi, penggunaan, lokasi log, dan batasan aplikasi.

**Hasil:** MVP siap dijalankan dari source. Pembuatan executable Windows menjadi tahap terpisah setelah MVP stabil.

## 13. Rencana Pengujian

- **Validasi:** URL host palsu, URL tidak didukung, input kosong, angka nol, dan angka negatif ditolak.
- **Konkurensi:** worker simulasi membuktikan browser aktif tidak melampaui batas, termasuk ketika satu sesi gagal.
- **Akuntansi sesi:** setiap sesi berakhir tepat satu kali; jumlah selesai + gagal + dibatalkan sama dengan target setelah run berakhir.
- **Durasi:** fixture video lokal menguji bahwa pause dan buffering tidak menambah waktu pemutaran yang dihitung.
- **Pembatalan:** Stop membatalkan antrean dan sesi aktif tanpa membuat sesi pengganti.
- **Pembersihan:** resource browser ditutup ketika sesi selesai, error, timeout, atau dibatalkan.
- **Isolasi data:** cookie dan storage pada fixture lokal dari sesi A tidak tersedia pada sesi B; pembersihan tidak menyentuh profil browser pribadi atau folder log.
- **Kegagalan cleanup:** penguncian file atau kegagalan penutupan menghasilkan status peringatan yang terlihat; tidak dilaporkan sebagai pembersihan sukses. Worker tidak membuka browser pengganti selama browser sebelumnya belum dipastikan berhenti.
- **Uji manual GUI:** tampilan tetap responsif dan log tersimpan saat run aktif.
- **Uji integrasi terbatas:** satu sesi pada video yang dikuasai pengguna untuk memeriksa kompatibilitas player YouTube.
- **Indikator pemutaran:** fixture lokal memastikan iklan, video salah, seek, dan player error tidak dianggap sebagai pemutaran konten target yang valid.
- **Monitor views:** fixture HTML mencakup counter naik, tetap, turun, baseline hilang, elemen hilang, angka ringkas, locale Indonesia/Inggris, angka ambigu, consent/login, timeout, dan hasil lama dari run sebelumnya. Tidak memerlukan kenaikan view sungguhan.
- **Pemisahan hasil:** pembacaan halaman gagal tidak menggagalkan sesi pemutaran; kenaikan counter tidak mengubah sesi gagal menjadi selesai.
- **Kontrol monitor:** hanya satu pembacaan aktif per run; Stop membatalkannya; cek manual tidak menambah sesi; gabungan jendela worker dan monitor tidak melampaui batas, termasuk saat batasnya 1.
- **Penjadwalan:** pemeriksaan dijadwalkan setiap 120 detik; keterlambatan akibat slot penuh dicatat dan tidak memicu tumpukan pengecekan susulan.

Perubahan counter view publik dicatat sebagai observasi statistik, bukan bukti bahwa sesi aplikasi diterima YouTube. Pengujian monitor memverifikasi pembacaan dan perhitungan selisih, bukan atribusi kenaikan.

## 14. Kriteria Selesai MVP

- Seluruh input dan tombol pada rancangan GUI tersedia dan berfungsi.
- GUI tetap responsif selama run.
- Batas browser aktif selalu ditaati.
- Durasi diukur dari pemutaran video, bukan hanya waktu halaman terbuka.
- Stop menghentikan antrean dan membersihkan browser milik run.
- Setiap sesi memiliki hasil akhir yang tercatat.
- Setiap sesi memakai context sementara baru; status pembersihan dicatat terpisah dari hasil pemutaran. Tidak ada profil pribadi atau folder log yang ikut dibersihkan.
- Log tampil di GUI dan tersimpan di folder `log/`.
- Ringkasan akhir membedakan selesai, gagal, dan dibatalkan.
- GUI memperlihatkan bukti kondisi player selain durasi menonton.
- Jika monitor diaktifkan, hasil pembacaan halaman, presisi angka, sumber, dan waktu pengecekan tampil serta tercatat di log; selisih hanya dihitung bila baseline dan pembanding sama-sama angka persis.
- Counter tetap, turun, terlambat, dan tidak tersedia dibedakan; tidak ada klaim atribusi view ke aplikasi.
- README menyediakan langkah instalasi dan penggunaan yang dapat diikuti.

## 15. Di Luar Lingkup MVP

- Jaminan bertambahnya view yang diakui YouTube.
- Proxy rotation, pemalsuan fingerprint, atau bypass CAPTCHA dan pembatasan platform.
- Login otomatis, penggunaan akun massal, dan pengelolaan cookie akun.
- Playlist, live stream, navigasi feed Shorts vertikal, penjadwalan, dan resume setelah aplikasi ditutup.
- Installer atau executable Windows.

Fokus implementasi pertama adalah GUI yang stabil, pengendalian browser yang terukur, Run/Stop yang bersih, dan log yang mudah ditelusuri.

## 16. Deteksi Pemutaran dan Perubahan Views

### A. Bukti pemutaran per sesi

Selain memenuhi durasi, worker memeriksa kondisi berikut secara berkala:

- Video ID halaman/player sesuai dengan video target; perpindahan ke video rekomendasi tidak dihitung.
- Elemen video tersedia, tidak memiliki error media, dan data media siap diputar.
- Player berada pada kondisi memutar; `currentTime` bergerak maju dan, bila tersedia, jumlah frame yang disajikan bertambah.
- Iklan yang terdeteksi tidak dihitung sebagai waktu pemutaran konten target. Jika identitas konten belum dapat dipastikan, statusnya `Belum terverifikasi` dan penghitungan ditunda sampai timeout.
- Buffering, pause, video berakhir terlalu cepat, halaman login, dan player error memiliki status berbeda.
- Lompatan posisi akibat seek tidak ditambahkan sebagai waktu menonton. Gunakan jam monotonik serta sampel posisi video untuk membatasi penambahan waktu valid; MVP menetapkan playback rate 1x.

Status sesi dapat bergerak dari `Membuka` → `Menunggu player` → `Memutar terverifikasi` → `Selesai`, atau berakhir sebagai `Gagal` / `Dibatalkan`. Indikator ini membuktikan kondisi pemutaran yang diamati aplikasi, bukan pencatatan view oleh YouTube. Deteksi iklan dan struktur player perlu diuji ulang bila halaman YouTube berubah.

### B. Sumber counter publik

Gunakan Playwright untuk membaca DOM halaman video publik. Tidak memanggil YouTube Data API, endpoint internal YouTube secara langsung, atau layanan counter pihak ketiga. Browser tetap melakukan request normal saat memuat halaman.

Urutan pembacaan:

1. Pastikan URL/video ID sesuai target dan halaman tidak sedang menampilkan consent, login, atau pembatasan akses.
2. Cari elemen views menggunakan locator yang dibatasi ke metadata video utama, bukan jumlah likes, komentar, atau video rekomendasi.
3. Bila diperlukan, buka detail deskripsi atau tooltip yang tersedia di UI untuk mencari angka lengkap. Ketersediaan angka lengkap tidak dijamin; selector ditetapkan dan diuji saat implementasi, bukan diasumsikan stabil.
4. Simpan teks asli, lokasi elemen, locale, waktu pembacaan, dan presisi angka.
5. Jika tersedia angka lengkap, parse menjadi integer nonnegatif dengan aturan locale yang jelas. Contoh format Indonesia `1.234 tayangan` dan Inggris `1,234 views` harus ditafsirkan berdasarkan locale, bukan sekadar membuang seluruh tanda baca.

Klasifikasi hasil:

- `exact`: angka lengkap yang dapat diparse tanpa ambiguitas; boleh dipakai untuk menghitung selisih.
- `abbreviated`: hanya tersedia teks ringkas seperti `1,2 rb` atau `1.2K`; tampilkan teks sebagai angka perkiraan, tanpa mengubahnya menjadi counter persis.
- `unavailable`: elemen hilang, angka ambigu, atau halaman terhalang; tampilkan alasan tanpa mengganti nilai menjadi nol.

Teks yang terbaca adalah snapshot halaman, bukan jaminan statistik terbaru di server. Angka ringkas yang tetap sama tidak membuktikan views tidak bertambah.

### C. Perhitungan dan interpretasi

```text
selisih_views = counter_terakhir_exact - counter_awal_exact
```

- Selisih positif: `Kenaikan counter teramati`.
- Selisih nol: `Belum ada perubahan counter teramati`.
- Selisih negatif: `Counter publik menurun`; pertahankan nilai negatif.
- Baseline atau pembacaan pembanding tidak tersedia/persis: `Perubahan belum dapat ditentukan secara akurat`.
- Jika salah satu pembacaan hanya angka ringkas, tampilkan teks awal dan terbaru tanpa selisih numerik. Jangan menyandingkan angka ringkas terbaru dengan selisih exact lama seolah-olah satu snapshot.
- Pembacaan terbaru gagal: tandai data sebelumnya sebagai lama, tampilkan waktu terakhir berhasil dan error terbaru.

**Batas kepastian:** angka pada halaman tidak memberi tanda bahwa satu sesi aplikasi menghasilkan satu view yang diterima. Kenaikan dapat berasal dari penonton lain. YouTube juga dapat menunda, membekukan, atau mengoreksi hitungan serta membuang pemutaran berkualitas rendah. Tidak ada janji waktu pasti pembaruan counter.

### D. Siklus monitor

- Satu monitor melayani satu run/video. Ambil baseline sebelum pemutaran dan jadwalkan pengecekan berikutnya setiap **120 detik** menggunakan jam monotonik.
- Setiap pembacaan memakai jendela dengan satu tab dan context sementara baru, agar memuat ulang halaman tanpa me-refresh tab sesi yang sedang ditonton. Jendela ini ditutup dan dibersihkan setelah pembacaan.
- Semua jendela, termasuk monitor, memakai satu pembatas bersama. Monitor yang sudah jatuh tempo mendapat prioritas pada slot berikutnya setelah sesi aktif selesai. Batas 1 berarti pemutaran dan pengecekan bergantian, bukan membuka jendela kedua.
- Jika terlambat karena slot penuh, tampilkan `Menunggu slot pengecekan` dan catat waktu jadwal serta waktu aktual. Lewati jadwal yang terlewat, jangan menumpuk pembacaan atau menjalankan beberapa sekaligus. Interval ini bukan jaminan counter diperbarui setiap 120 detik.
- Monitor tidak mengeklik Play, mencoba mencegah autoplay, dan segera menjeda player bila mulai berjalan. Jika pencegahan playback tidak dapat diterapkan, batalkan pembacaan. Jangan mengklaim kunjungan halaman monitor pasti tidak memengaruhi pencatatan YouTube.
- Pembacaan dibatasi 30 detik setelah memperoleh slot. Koneksi gagal atau selector tidak ditemukan dicatat, lalu tunggu jadwal berikutnya. Halaman pembatasan/CAPTCHA tidak dilewati; hentikan pengecekan otomatis untuk run tersebut dan tampilkan alasannya.
- Run normal berakhir setelah satu percobaan pembacaan akhir dengan timeout; tidak terus membuka sesi sampai counter naik.
- Setelah run, pengguna dapat melakukan cek manual selama aplikasi masih terbuka. Pengecekan ulang memakai baseline run yang dipilih dan tidak membuat baseline baru. Jendela monitor sementara boleh terbuka saat cek manual, tetapi tidak menambah sesi target.
- Tidak ada polling tersembunyi setelah aplikasi ditutup. Simpan baseline dan snapshot dalam log agar hasil tetap dapat ditinjau.

### E. Rujukan teknis

- [Playwright Python — locator dan pembacaan elemen](https://playwright.dev/python/docs/locators)
- [Playwright Python — Locator API](https://playwright.dev/python/docs/api/class-locator)
- [YouTube Help — cara metrik interaksi dihitung](https://support.google.com/youtube/answer/2991785)

Pendekatan MVP adalah pembacaan tampilan halaman melalui Playwright tanpa API key. Pembacaan live dan selector belum diuji karena perubahan ini hanya memperbarui rencana. Perubahan UI YouTube dapat memerlukan pemeliharaan locator.

## 17. Isolasi dan Pembersihan Data Sesi

### Tujuan dan batasnya

Pembersihan diperlukan untuk menjaga privasi lokal, membatasi sisa file sementara, dan memastikan sesi berikutnya tidak mewarisi state sesi sebelumnya. Pembersihan bukan jaminan anonim atau tidak terdeteksi, tidak menghapus catatan kunjungan di server YouTube, dan tidak membuat sesi otomatis menjadi view yang valid.

Gunakan context nonpersisten baru melalui `browser.new_context()` untuk setiap sesi. Menurut dokumentasi Playwright, context ini tidak menyimpan data browsing ke disk. Jangan memakai profil Chrome pribadi, persistent context, atau memuat ulang `storage_state` dari sesi sebelumnya.

### Data yang ditangani

- Cookie, local storage, session storage, IndexedDB, dan state situs diisolasi dalam context sementara; context dibuang setelah sesi berakhir.
- History navigasi dan cache sesi tidak digunakan kembali pada sesi berikutnya. Jangan membuat database history persisten.
- Tidak perlu melakukan clear-cookie dan clear-cache berulang selama video sedang diputar. Menutup dan membuang context adalah mekanisme utama pengakhiran state sesi.
- Download tidak diaktifkan sebagai fitur MVP. Trace, HAR, rekaman video, screenshot, dan ekspor storage tidak disimpan secara default.
- Jika implementasi membuat file sementara tambahan, setiap sesi memiliki direktori sendiri di root temporary aplikasi. Direktori tersebut dibersihkan setelah semua handle dan proses yang menggunakannya ditutup.
- File log di `log/`, konfigurasi, dan kredensial lokal tetap dipertahankan. Riwayat aktivitas aplikasi pada log memang sengaja disimpan sesuai kebutuhan pengguna.

### Urutan pembersihan

1. Selesaikan pencatatan hasil pemutaran atau pembatalan.
2. Jalankan penutupan context, lalu browser, dengan timeout terpisah di blok `finally`. Kegagalan menutup context tidak boleh melewatkan upaya menutup browser.
3. Verifikasi browser milik sesi sudah berhenti sebelum membuka penggantinya; jika tidak dapat dipastikan, hentikan worker dan tampilkan error.
4. Sebelum menghapus direktori sementara, resolve path absolut dan pastikan target merupakan subdirektori sesi yang terdaftar di root temporary aplikasi. Jangan mengikuti symlink/junction ke luar root atau menghapus root itu sendiri.
5. Hapus hanya file sementara milik sesi tersebut. Jika masih terkunci, lakukan retry terbatas, lalu catat path dan alasan kegagalan untuk penanganan berikutnya.
6. Kirim status cleanup ke GUI dan log: `Membersihkan`, `Selesai`, atau `Pembersihan tidak lengkap`.

Urutan yang sama berlaku setelah durasi terpenuhi, player error, timeout, Stop, dan penutupan aplikasi. Jika aplikasi crash, pembersihan langsung tidak dijamin. Pada startup berikutnya, periksa sisa direktori sesi milik aplikasi dan bersihkan hanya setelah kepemilikan path serta ketiadaan proses aktif dapat dipastikan; bila ragu, pertahankan dan catat peringatan.

Hasil pemutaran dan hasil cleanup adalah dua hal berbeda. Contoh: `Pemutaran selesai; pembersihan tidak lengkap`. Jangan menyembunyikan kegagalan cleanup atau mengganti hasil pemutaran menjadi sukses hanya karena file sudah dibersihkan. Penghapusan file biasa juga bukan jaminan penghapusan forensik seluruh jejak pada perangkat.

### Tampilan GUI

Tampilkan keterangan tetap `Data sesi sementara; dibersihkan setelah setiap sesi` dan status cleanup per worker. Jadikan perilaku ini default MVP, tanpa opsi memakai profil pribadi atau klaim `anti-detect`.

Rujukan: [Playwright Python — context nonpersisten](https://playwright.dev/python/docs/api/class-browsercontext), [Playwright Python — tutup context sebelum browser](https://playwright.dev/python/docs/api/class-browser).


## 18. Status implementasi MVP

Fitur inti sudah diimplementasikan: GUI, Run/Stop, Shorts asli dengan monitor melalui watch, batas jendela bersama monitor, status sesi, progress, logging, pembacaan DOM 120 detik, presisi angka, data lama saat error, dan context sementara. Struktur aktual ada pada README.md; beberapa tanggung jawab browser tetap digabung dalam runner agar lifecycle resource terpusat.

Validasi otomatis meliputi parser, accounting sesi, Stop saat baseline, batas monitor/worker, disk error, kegagalan cleanup, video lokal, isolasi storage, serta Run/Stop/Run dan tutup GUI. Pengujian tidak memakai kenaikan views sebagai kriteria keberhasilan.

Pembersihan file tambahan pada bagian 17 bersifat kondisional: implementasi tidak membuat file sementara tambahan sendiri. Profile sementara dikelola Playwright. Pemulihan crash tidak menghapus folder temporary yang kepemilikannya tidak dapat dibuktikan. Pengujian terbaru terhadap UI YouTube live tetap belum dilakukan; detail batas dukungan ada pada README.md.
