# Magic Chess Go Go Hybrid Optimizer

Project ini memakai algoritma hybrid untuk memberi rekomendasi hero Magic Chess Go Go berdasarkan kondisi board, shop, synergy, dan skor carry. Tampilan akhirnya berupa dashboard HTML statis yang dibuat dari `main.py`, jadi project ini tidak memakai Streamlit.

Dataset utama yang digunakan:

- `data/raw/heroes_id.json`
- `data/raw/synergies_id.json`

Dataset `battle` dan `power` tidak dipakai agar analisis tetap fokus ke hero dan synergy.

## Inti Revisi

Alur simulasi dibuat agar mirip proses refresh shop di Magic Chess:

1. Board dibuat secara random.
2. Shop melakukan refresh random berisi 5 hero.
3. Algoritma hanya menilai hero yang muncul di shop tersebut.
4. Output menampilkan visualisasi shop, ranking rekomendasi, bobot adaptive, dan formula skor.
5. Dashboard HTML menyediakan tombol `Random Refresh` untuk mengganti sampel hasil simulasi yang sudah digenerate.

## Struktur Project

```text
magic-chess-gogo/
|-- main.py                         # Generator dashboard HTML
|-- data/
|   |-- heroes.py                   # Loader dataset hero
|   |-- synergies.py                # Loader dataset synergy
|   `-- raw/
|       |-- heroes_id.json
|       |-- heroes_id.csv
|       |-- synergies_id.json
|       `-- synergies_id.csv
|-- core/
|   `-- board.py
|-- algorithms/
|   |-- adaptive.py
|   |-- game_simulator.py
|   |-- greedy.py
|   |-- heuristic.py
|   |-- hybrid.py
|   `-- shop.py
`-- output/
    |-- index.html                  # Dashboard utama
    |-- dataset.html                # Redirect ke tab dataset
    |-- data.js                     # Data hasil simulasi
    |-- dataset-data.js             # Data hero dan synergy
    |-- script.js
    `-- styles.css
```

## Cara Menjalankan

Jalankan generator HTML:

```bash
python main.py
```

Setelah dijalankan, file dashboard akan dibuat atau diperbarui di:

```text
output/index.html
```

Buka `output/index.html` di browser untuk melihat dashboard. File `output/dataset.html` akan langsung mengarah ke tab dataset di dashboard yang sama.

Project ini hanya memakai modul Python standar, jadi tidak perlu install Streamlit atau dependency tambahan.

## Cara Generate Grafik Analisis

Tool grafik statis tersedia di:

```bash
python tools/generate_grafik.py
```

Output yang dibuat:

```text
output/grafik.html
output/grafik/*.svg
output/grafik/manifest.json
```

Grafik mencakup distribusi cost hero, distribusi role, top power index, jumlah hero per sinergi, perbandingan final power strategi, timeline gold checkpoint, dan bobot adaptive per strategi.

Opsi yang bisa dipakai:

```bash
python tools/generate_grafik.py --samples 50 --seed 20260510
```

## Letak Algoritma

Alur algoritma ada di beberapa file:

- `algorithms/shop.py`: membuat random shop / refresh.
- `algorithms/greedy.py`: menghitung nilai langsung hero.
- `algorithms/heuristic.py`: menghitung potensi lanjutan hero.
- `algorithms/adaptive.py`: mengubah bobot sesuai kondisi board.
- `algorithms/hybrid.py`: menggabungkan skor menjadi rekomendasi akhir.
- `algorithms/game_simulator.py`: menjalankan simulasi beberapa profil strategi.

Formula utama:

```text
Hybrid Score = alpha * Greedy + beta * Heuristic + gamma * Carry
```

Nilai `alpha`, `beta`, dan `gamma` berubah sesuai kondisi board.

## Catatan

Nilai `role`, `carry_score`, `skill_power`, dan `power_index` dibuat secara turunan dari dataset karena file hero baru tidak menyediakan kolom tersebut secara langsung. Nilai ini dipakai supaya algoritma tetap bisa berjalan dengan dataset baru.
