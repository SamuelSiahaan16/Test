# YouTube Playback Lab

MVP Python GUI untuk mempelajari antrean browser, pemutaran, pembatalan, dan logging. Sesi selesai tidak menjamin view diterima YouTube; kenaikan counter tidak dapat diatribusikan ke aplikasi.

## Menjalankan di Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m playwright install chromium
.\.venv\Scripts\python main.py
```

Jika `.venv` sudah tersedia, cukup jalankan perintah terakhir.

## Mencoba pertama kali

1. Biarkan **Mode simulasi** tercentang. URL boleh kosong.
2. Atur target 5 sesi, maksimal 2 jendela, dan durasi 3 detik.
3. Tekan Run. Dua sesi simulasi berjalan bersamaan tanpa browser.
4. Coba Stop saat berjalan. Hasil sesi dan pembatalan muncul di log.
5. Untuk menguji browser, matikan simulasi, masukkan URL video yang kamu kuasai, lalu mulai dengan satu sesi dan satu jendela.

## Membaca kode

- `main.py`: entry point aplikasi.
- `app/gui/main_window.py`: form, tabel sesi, progress, Run/Stop, dan log GUI.
- `app/core/runner.py`: QThread, antrean asyncio, browser, pembatalan, monitor, cleanup.
- `app/core/playback_probe.py`: perhitungan waktu pemutaran yang terverifikasi.
- `app/core/view_count_monitor.py`: locator metadata, ekspansi deskripsi, parser angka Indonesia/Inggris.
- `app/utils/validators.py`: validasi URL serta aturan durasi Shorts.
- `app/utils/logging_setup.py`: penulisan log dengan deteksi kegagalan disk.
- `tests/`: tes logika, Chromium lokal, dan lifecycle GUI.

Alternatif instalasi: jalankan `setup.ps1`, lalu `run.ps1`. Versi dependency dikunci pada versi yang diuji. Python pengujian: 3.13 di Windows.

## Perilaku penting

- URL `https://www.youtube.com/shorts/VIDEO_ID` didukung, termasuk parameter share. Sesi playback membuka `/shorts/VIDEO_ID` dengan player Shorts aktif. Monitor views tetap membaca halaman `watch?v=VIDEO_ID` secara terpisah. Aplikasi tidak melakukan scroll ke Shorts lain.
- Untuk input URL Shorts, target efektif adalah nilai terkecil antara durasi yang diminta dan panjang video. Video tidak di-loop; akhir video diterima hanya jika waktu pemutaran terverifikasi mendekati target (toleransi sampling maksimal 0,75 detik). URL watch/youtu.be tidak otomatis diklasifikasikan sebagai Shorts.

- Setiap sesi menggunakan jendela Chromium tersendiri dengan satu tab dan context nonpersisten.
- Monitor menggunakan slot jendela yang sama. Saat semua slot penuh, pengecekan 120 detik menunggu sesi selesai.
- Monitor berusaha mencegah autoplay. Kunjungan halaman tetap terlihat oleh situs dan tidak dijamin bebas pengaruh terhadap statistik.
- Pemutaran memeriksa ID video, status iklan, posisi media, buffering, dan error. Seek tidak dihitung sebagai durasi normal.
- Stop membatalkan pekerjaan aktif dan antrean, lalu menutup browser. Penutupan dapat memerlukan beberapa detik.
- Log berada di folder `log/` di samping `main.py`. Folder tersebut harus dapat ditulis. Log tidak ikut dihapus saat context browser dibuang.
- Browser menggunakan profil sementara yang dikelola Playwright. Profil Chrome pribadi tidak dipakai.

## Monitor dan kondisi sesi

Tabel menampilkan kondisi tiap sesi: membuka, menunggu player, iklan, buffering, pause, memutar terverifikasi, selesai, gagal, dibatalkan, serta cleanup. Tabel dibatasi 250 baris dan log GUI 2.000 baris; file log menyimpan seluruh pesan.

Monitor membaca metadata dari halaman watch, mencoba membuka detail deskripsi dan membaca judul/tooltip elemen. Parser membedakan angka lengkap, ringkas, dan tidak tersedia. Selisih hanya dihitung jika baseline dan angka terbaru sama-sama lengkap. Baseline gagal tidak diganti dengan data tengah run. Cek manual mempertahankan baseline run terakhir.

Jika pengecekan gagal, data terakhir beserta waktunya tetap ditampilkan sebagai data lama. Consent, login, atau pembatasan yang terdeteksi menghentikan monitor otomatis. Interval 120 detik dapat terlambat jika semua slot jendela penuh.

## Pembersihan dan error

Jika player menampilkan “Something went wrong”, pilih **Google Chrome terpasang** pada pilihan Browser untuk membandingkan kompatibilitas dengan Chromium bawaan. Chrome harus sudah terpasang; aplikasi memakai context sementara, bukan profil pribadi Chrome. Tidak ada perpindahan browser otomatis atau jaminan error YouTube teratasi.

Log error sesi sekarang memuat versi browser, sampel player terakhir, dan ringkasan kegagalan koneksi/status HTTP. Query URL media, cookie, dan isi respons tidak direkam. Error HTTP tertentu dapat membantu diagnosis, tetapi tidak dengan sendirinya membuktikan penyebab kegagalan. Mulai diagnosis dengan satu sesi dan satu jendela.

Context nonpersisten dan browser ditutup saat sesi selesai, gagal, atau dibatalkan. Penggunaan profil sementara dikelola Playwright; aplikasi tidak mengekspor storage, trace, download, screenshot, atau file cache tambahan. Tidak ada penghapusan direktori profil Chrome pribadi. Kegagalan menutup browser menghentikan run agar tidak membuat browser pengganti melebihi batas.

Crash/power-off tidak menjamin pembersihan sementara. Aplikasi tidak menebak kepemilikan lalu menghapus folder temporary sistem; sisa temporary yang dikelola Playwright/OS dapat tetap ada setelah crash. Log sengaja dipertahankan. Pembersihan lokal tidak menghapus catatan server.

Kegagalan menulis log menghentikan run secara terkendali. Tombol **Buka folder log** membuka lokasi file untuk diagnosis. Stop dapat memerlukan waktu penutupan browser; GUI tetap responsif. Menutup jendela saat run aktif menjalankan Stop dan menunggu worker selesai.

## Batas dukungan

- Shorts dibuka melalui tampilan Shorts asli; navigasi/scroll ke video berikutnya tidak didukung. Playlist, live stream, login akun, serta installer/executable tidak termasuk MVP.
- Struktur halaman YouTube dapat berubah. Pembacaan metadata dan iklan memakai elemen halaman/player, sehingga perlu pemeliharaan jika UI berubah. Tidak ada fallback API tersembunyi.
- Pengguna telah melaporkan pemutaran versi sebelumnya berhasil. Verifikasi otomatis versi ini menggunakan fixture lokal dan Chromium sungguhan; belum ada pengujian YouTube live terbaru pada video milik pengguna.
- Tidak ada jaminan kenaikan views atau atribusi counter ke sesi aplikasi.

## Pengujian lokal

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Pengujian lokal tidak membuka YouTube dan tidak membuktikan view bertambah.


Uji diagnosis 10 November 2026: Chrome terpasang juga menunjukkan error YouTube setelah sekitar 40 detik pada halaman watch video pengguna. Ini belum menetapkan penyebab. Dukungan halaman Shorts asli kemudian ditambahkan dan diuji dengan fixture Chromium lokal; uji live Shorts dicatat terpisah pada log bila dijalankan.
