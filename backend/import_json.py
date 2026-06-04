"""
JSON'dan test savollarini bazaga import qilish.

Kutiladigan format (ro'yxat):
    [
      {
        "id": 1,
        "question": "Savol matni?",
        "answer_a": "Variant A",
        "answer_b": "Variant B",
        "answer_c": "",            <- bo'sh variantlar tashlab yuboriladi
        "answer_d": "",
        "correct": "A"             <- to'g'ri javob harfi
      },
      ...
    ]

Variantlar har savol uchun barqaror (id seed) aralashtiriladi —
to'g'ri javob doim bir xil harfda turmasligi uchun. correct_index mos saqlanadi.

Ishga tushirish (docker ichida):
    docker cp test.json backend-web-1:/app/
    docker cp import_json.py backend-web-1:/app/
    docker compose exec -T web python import_json.py test.json \
        --title "Kiberxavfsizlik testi" --time-limit 60

Qayta ishga tushirilsa: shu nomli test o'chirilib, qaytadan yaratiladi.
"""
import argparse
import json
import os
import random
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction

from exams.models import Question, Test

ANSWER_KEYS = ["answer_a", "answer_b", "answer_c", "answer_d", "answer_e", "answer_f"]
LETTERS = "ABCDEF"


def parse_questions(items: list[dict]) -> list[dict]:
    """JSON elementlari -> [{order, text, options, correct_index}]."""
    cleaned = []
    for i, item in enumerate(items, start=1):
        order = int(item.get("id") or i)
        text = (item.get("question") or "").strip()
        correct_letter = (item.get("correct") or "A").strip().upper()

        if not text:
            print(f"  ! {order}-savol: matn bo'sh — tashlab ketildi")
            continue

        # (matn, is_correct) juftliklari; bo'shlar tashlanadi
        opts = []
        for letter, key in zip(LETTERS, ANSWER_KEYS):
            val = (item.get(key) or "").strip()
            if val:
                opts.append((val, letter == correct_letter))

        if len(opts) < 2:
            print(f"  ! {order}-savol: 2 tadan kam variant — tashlab ketildi")
            continue
        if not any(c for _, c in opts):
            print(f"  ! {order}-savol: to'g'ri javob ({correct_letter}) bo'sh/yo'q — tashlab ketildi")
            continue

        # Barqaror aralashtirish (har safar bir xil natija — order seed)
        rng = random.Random(order * 9973)
        rng.shuffle(opts)
        correct_index = next(i for i, (_, c) in enumerate(opts) if c)

        cleaned.append({
            "order": order,
            "text": text,
            "options": [t for t, _ in opts],
            "correct_index": correct_index,
        })
    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser(description="JSON'dan savollarni import qilish")
    parser.add_argument("json_file", help="JSON fayl yo'li")
    parser.add_argument("--title", default="Kiberxavfsizlik testi",
                        help="Test sarlavhasi (mavjud bo'lsa qayta yaratiladi)")
    parser.add_argument("--time-limit", type=int, default=25,
                        help="Imtihon vaqti, daqiqa (default: 25)")
    parser.add_argument("--description", default="", help="Test tavsifi")
    parser.add_argument("--if-missing", action="store_true",
                        help="Test allaqachon mavjud bo'lsa hech narsa qilmaslik "
                             "(server startidagi avto-import uchun)")
    args = parser.parse_args()

    if args.if_missing and Test.objects.filter(title=args.title).exists():
        existing = Test.objects.get(title=args.title)
        print(f"O'tkazildi: '{args.title}' allaqachon mavjud "
              f"({existing.questions.count()} ta savol).")
        return 0

    if not os.path.exists(args.json_file):
        print(f"XATO: fayl topilmadi: {args.json_file}")
        return 1

    print(f"O'qilmoqda: {args.json_file}")
    with open(args.json_file, encoding="utf-8-sig") as f:
        items = json.load(f)
    if not isinstance(items, list):
        print("XATO: JSON ildizi ro'yxat bo'lishi kerak.")
        return 1

    questions = parse_questions(items)
    print(f"Topildi: {len(questions)} ta yaroqli savol (JSON'da {len(items)} ta element)")
    if not questions:
        print("XATO: savol topilmadi — format mos emas.")
        return 1

    with transaction.atomic():
        old = Test.objects.filter(title=args.title).first()
        if old:
            print(f"Mavjud '{args.title}' testi o'chirilmoqda "
                  f"(savollari: {old.questions.count()})")
            old.delete()

        test = Test.objects.create(
            title=args.title,
            description=args.description or f"{len(questions)} ta savol (JSON'dan import)",
            time_limit_min=args.time_limit,
            is_active=True,
        )
        Question.objects.bulk_create([
            Question(
                test=test,
                order=q["order"],
                text=q["text"],
                options=q["options"],
                correct_index=q["correct_index"],
            )
            for q in questions
        ])

    # Tekshiruv: to'g'ri javob taqsimoti (hammasi bitta harfda emas)
    dist = {}
    for q in questions:
        letter = LETTERS[q["correct_index"]]
        dist[letter] = dist.get(letter, 0) + 1
    print(f"OK: '{test.title}' (id={test.id}) — {test.questions.count()} ta savol, "
          f"{args.time_limit} daqiqa")
    print(f"To'g'ri javob taqsimoti: {dict(sorted(dist.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
