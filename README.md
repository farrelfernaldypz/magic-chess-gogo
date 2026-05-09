# Magic Chess Random Refresh Dashboard

Project ini sudah diperbaiki agar memakai dataset baru patch `1.2.54` dan hanya memakai dua dataset utama:

- `data/raw/heroes_id.json`
- `data/raw/synergies_id.json`

Dataset `battle` dan `power` tidak dipakai agar analisis tetap fokus ke hero dan synergy.

## Inti Revisi Terbaru

Versi sebelumnya terasa "itu-itu terus" karena skenario board masih dibuat manual, misalnya Exorcist lalu KOF. Pada versi ini alurnya sudah dibuat lebih mirip Magic Chess:

1. Board bisa dibuat random.
2. Shop melakukan refresh random berisi 5 hero.
3. Algoritma hanya menilai hero yang muncul di shop tersebut.
4. Output menampilkan visualisasi shop, ranking rekomendasi, bobot adaptive, dan formula skor.
5. Tombol refresh tersedia di dashboard Streamlit.

## Struktur Project

```text
Magic Chess/
├── main.py                         # Membuat dashboard HTML visual dengan sampel random refresh
├── app.py                          # Dashboard interaktif Streamlit dengan tombol refresh
├── requirements.txt
├── data/
│   ├── heroes.py                   # Loader dataset hero baru
│   ├── synergies.py                # Loader dataset synergy baru
│   └── raw/
│       ├── heroes_id.json
│       ├── heroes_id.csv
│       ├── synergies_id.json
│       └── synergies_id.csv
├── core/
│   └── board.py
└── algorithms/
    ├── greedy.py
    ├── heuristic.py
    ├── adaptive.py
    ├── hybrid.py
    └── shop.py                     # Random shop / refresh simulator
```

## Cara Menjalankan Output Visual HTML

```bash
python main.py
```

Setelah dijalankan, file visual akan dibuat di:

```text
output/magic_chess_dashboard.html
```

Dashboard HTML berisi banyak sampel random refresh. Tombol `Random Refresh` pada HTML akan mengganti tampilan ke sampel refresh lain yang sudah digenerate saat `python main.py` dijalankan.

## Cara Menjalankan Dashboard Interaktif Streamlit

```bash
pip install -r requirements.txt
streamlit run app.py
```

Di Streamlit, gunakan tombol:

- `Refresh Random Board + Shop` untuk mengganti board dan shop sekaligus.
- `Refresh Shop Saja` untuk mengganti shop dari board yang sama.

## Letak Algoritma

Alur algoritma ada di beberapa file:

- `algorithms/shop.py`: membuat random shop / refresh.
- `algorithms/greedy.py`: menghitung nilai langsung hero.
- `algorithms/heuristic.py`: menghitung potensi lanjutan hero.
- `algorithms/adaptive.py`: mengubah bobot sesuai kondisi board.
- `algorithms/hybrid.py`: menggabungkan skor menjadi rekomendasi akhir.

Formula utama:

```text
Hybrid Score = α × Greedy + β × Heuristic + γ × Carry
```

Nilai α, β, dan γ berubah sesuai kondisi board.

## Catatan

Nilai `role`, `carry_score`, `skill_power`, dan `power_index` dibuat secara turunan dari dataset karena file hero baru tidak menyediakan kolom tersebut secara langsung. Nilai ini dipakai supaya algoritma lama tetap bisa berjalan dengan dataset baru.
