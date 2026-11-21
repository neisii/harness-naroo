# Copyright 2026 Baek Ga-hui (neisii) - https://github.com/neisii/harness-naroo
# SPDX-License-Identifier: Apache-2.0
# 가이드 9장 실습: 각자 통과한 두 브랜치가, 충돌 없이 합쳐진 뒤 깨진다.
# 실행: bash examples/merge_break_demo.sh
# 필요한 것: git, python3. 임시 폴더에서만 작업하고 끝나면 그 경로를 알려 준다.
set -e

LAB="$(mktemp -d)"
cd "$LAB"
git init -q shop && cd shop
git checkout -q -b main
git config user.name lab
git config user.email lab@example.com

# 처음 상태: 합계를 구하는 total()
cat > price.py <<'P'
def total(price, qty):
    return price * qty
P
cat > test_shop.py <<'P'
from price import total
assert total(1000, 3) == 3000
print("  합계 통과")
P
git add . && git commit -qm "처음 상태"

# A: total()의 이름을 total_price()로 바꾸고, 자기가 아는 호출부는 다 고친다
git checkout -q -b feature/A
cat > price.py <<'P'
def total_price(price, qty):
    return price * qty
P
cat > test_shop.py <<'P'
from price import total_price
assert total_price(1000, 3) == 3000
print("  합계 통과")
P
git commit -qam "A: total을 total_price로 이름 바꿈"
echo "== A 브랜치 테스트"
python3 test_shop.py

# B: main에서 갈라져, 옛 이름 total()을 쓰는 영수증 기능을 새로 만든다
git checkout -q main
git checkout -q -b feature/B
cat > receipt.py <<'P'
from price import total
def receipt(price, qty):
    return f"합계 {total(price, qty)}원"
P
cat >> test_shop.py <<'P'
from receipt import receipt
assert receipt(1000, 3) == "합계 3000원"
print("  영수증 통과")
P
git add . && git commit -qm "B: 영수증 기능 추가"
echo "== B 브랜치 테스트"
python3 test_shop.py

# 둘을 main에 합친다
git checkout -q main
git merge -q --no-edit feature/A
git merge -q --no-edit feature/B
echo "== 병합: 충돌 없음"

echo "== 병합한 main 테스트"
if python3 test_shop.py 2>err.txt; then
  echo "  (예상과 달리 통과)"
else
  echo "  실패: $(tail -n 1 err.txt)"
fi

echo
echo "실습 폴더: $LAB/shop (다 봤으면 지워도 된다)"
