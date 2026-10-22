# DUNGEON CRAWLER 2D - REAL-TIME ACTION ROGUELIKE RPG (PYTHON + PYGAME CE)

Dự án game 2D Real-Time Grid-Based Action Roguelike RPG xây dựng bằng Python 3.x và `pygame-ce`.
Kết hợp mượt mà giữa **di chuyển thời gian thực (WASD / Dash)**, **hệ thống Stamina**, **cơ chế Telegraph né đòn (Read -> Dodge -> Punish)**, **xây dựng Relic Build synergy**, và **hệ thống Boss Room State Machine an toàn**.

---

## 1. Cấu trúc thư mục hoàn chỉnh

```text
dungeon_game/
├── main.py                     # Điểm khởi chạy game
├── settings.py                 # Cấu hình toàn cục, Stamina costs, Bảng EXP, Độ khó
├── requirements.txt            # Thư viện phụ thuộc (pygame-ce >= 2.4.0)
├── README.md                   # Tài liệu hướng dẫn và báo cáo kỹ thuật
│
├── core/                       # Hệ thống engine hạt nhân
│   ├── game.py                 # Real-Time Game Loop (Update 60 FPS, Event Dispatcher, Frustum Culling)
│   ├── camera.py               # Camera 2D Lerp, Frustum Culling, Screen Shake
│   ├── collision.py            # Hệ thống va chạm AABB, Move & Slide trượt tường mượt mà
│   ├── animation.py            # Sprite generator thủ tục chuẩn Alpha (SRCALPHA, No purple bug)
│   ├── sound.py                # Sound Manager tổng hợp sóng âm thanh retro
│   └── save_manager.py         # Lưu / Tải game dạng JSON
│
├── dungeon/                    # Thuật toán sinh màn chơi
│   ├── bsp.py                  # Cây Binary Space Partitioning (BSPNode)
│   ├── room.py                 # Quản lý hình học Room dạng gần vuông (Square rooms)
│   └── dungeon_generator.py    # Dungeon Generator: Boss Arena lớn, Cửa sắt Gate, Treasure room (<=2 chest), Validation Reachability
│
├── ai/                         # Trí tuệ nhân tạo Real-Time
│   ├── pathfinding.py          # Thuật toán A* Pathfinding theo Grid + Obstacles + Gates
│   ├── state_machine.py        # Generic Finite State Machine (FSM) Real-Time
│   └── states.py               # FSM States (Idle, Patrol, Chase, KeepDistance/Kiting, Attack, Hurt, Dead)
│
├── entities/                   # Thực thể trong game
│   ├── base.py                 # Entity cơ sở: tọa độ liên tục pos_x/pos_y + Grid mapping (grid_x, grid_y)
│   ├── class_data.py           # Thiết kế ClassData (Knight, Archer, Mage)
│   ├── player.py               # Player (WASD liên tục, Stamina, Dash né đòn, Special Skills: Shield Bash / Roll Shot / Blink)
│   ├── enemy.py                # 5 loại quái (Goblin, Skeleton, Orc, ArcherEnemy, MageEnemy)
│   ├── boss.py                 # Boss Malakor: Bounded 100% trong Boss Room, Telegraph 3x3, Hắc ma thuật, Triệu hồi quái
│   └── npc.py                  # NPC Thương nhân trong Shop Room
│
├── combat/                     # Hệ thống chiến đấu Action Roguelike
│   ├── weapon.py               # Melee (Sword, Axe, Greatsword, Spear) & Ranged (Bow, Staff)
│   ├── projectile.py           # Hệ thống đạn bay (Arrows, Magic bolts, Fireballs)
│   ├── telegraph.py            # Vùng cảnh báo nguy hiểm Telegraph (Read -> Dodge -> Punish)
│   ├── damage.py               # Floating Damage Numbers (Text bay, Critical Hit)
│   └── combat_system.py        # Melee Slash Arc, Hit flash trắng, Particles, Projectiles collision
│
├── items/                      # Vật phẩm, Cổ vật và hòm đồ
│   ├── item.py                 # Item cơ sở
│   ├── potion.py               # Các loại thuốc (Health, Mana, Speed, Strength)
│   ├── relic.py                # Hệ thống Cổ vật Relic (Flame Core, Thunder Ring, Frost Heart, Blood Charm, Iron Shell, Void Crystal)
│   ├── inventory.py            # Quản lý túi đồ, phím tắt sử dụng
│   └── loot.py                 # Bảng rơi đồ quái, rương, và BossLootTable (Drop Relic)
│
├── world/                      # Thế giới game
│   ├── tilemap.py              # Grid Tilemap, Line-of-Sight Raycasting, Fog of War
│   ├── obstacle.py             # Thùng gỗ Barrel phá vỡ được (1-3 Gold, 1 Potion) & Trụ đá Pillar
│   ├── ground_item.py          # Vật phẩm rơi trên sàn (GroundItem) để người chơi tự nhặt
│   ├── gate.py                 # Cửa sắt Gate & BossRoomController (FSM: ENTERING -> SPAWN -> ANNOUNCEMENT -> LOCKING -> FIGHTING)
│   ├── chest.py                # Rương báu mở bằng phím tương tác
│   └── door.py                 # Cửa thường và Bẫy chông (Trap)
│
├── progression/                # Tiến trình nhân vật
│   ├── level_system.py         # EXP Curve, Multiple Level-up Resolution
│   └── level_up_modal.py       # Modal UI tạm dừng game khi lên cấp (+10 Max HP, +2 ATK, +1 DEF, +10 SPD, +15 Stamina)
│
└── ui/                         # Giao diện người dùng
    ├── hud.py                  # HUD Stats + Thanh Relic Inventory Bar + Tooltip box khi rê chuột
    ├── boss_bar.py             # Thanh máu Boss kèm Phase
    ├── inventory_ui.py         # Màn hình túi đồ và bảng chỉ số nhân vật
    ├── menu.py                 # Main Menu, Class Selection UI, Pause, Game Over, Victory
    └── minimap.py              # Bản đồ thu nhỏ Radar (Fog of War)
```

---

## 2. Hướng dẫn cài đặt và khởi chạy game

### Cài đặt thư viện:
```bash
pip install -r requirements.txt
```

### Chạy game:
```bash
python main.py
```

---

## 3. Bảng phím điều khiển (Real-Time Action Roguelike)

| Phím | Hành động |
|---|---|
| **A / D** hoặc **Mũi tên Trái / Phải** | Lựa chọn Class trong màn hình Select |
| **W, A, S, D** hoặc **Mũi tên** | Di chuyển nhân vật liên tục thời gian thực (trượt tường mượt mà) |
| **SPACE** | **Dash Né Đòn**: Lướt nhanh né đòn bất tử (Tiêu hao 25 Stamina) |
| **K** / **J** / **Chuột trái** | Tấn công liên tục theo cooldown (Vung kiếm Melee Slash Arc / Bắn Ranged Projectile) |
| **F** | **Kỹ năng đặc biệt Class** (Knight: Shield Bash, Archer: Roll Shot, Mage: Blink Teleport) / Tương tác |
| **Q** hoặc **1** | Uống nhanh bình máu (Health Potion x3 khởi đầu) |
| **TAB** | Đổi vũ khí tiếp theo trong túi đồ |
| **E** | Mở rương (Chest), Mua đồ NPC, Qua cổng sang tầng mới |
| **I** | Bật / Tắt túi đồ (Inventory & Equipment) |
| **Hover chuột vào icon Relic** | Xem bảng Tooltip chi tiết: Tên, Phẩm cấp Rarity, Mô tả, Hiệu ứng thực tế |
| **1, 2, 3, 4, 5** | Chọn nâng cấp trong màn hình **LEVEL UP!** modal |
| **P / ESC** | Tạm dừng (Pause game) |
| **F3** | Bật / Tắt **Debug Mode** (FPS, Tọa độ, Stamina, Attack Cooldown, Boss State, Vùng Telegraph) |
| **F4** | Bật / Tắt **Sprite Diagnostics Mode** (Kiểm tra và xem live sample từ các sprite sheet PNG) |

---

## 4. Các tính năng & Cơ chế Gameplay cốt lõi

### 4.1. Hệ thống Boss Room FSM & Khóa Cổng An Toàn
- Cửa sắt Gate chỉ đóng khi Player đã tiến vào phòng và Boss đã xuất hiện kèm banner thông báo:
  - `INACTIVE` -> `ENTERING` -> `BOSS_SPAWNING` -> `ANNOUNCEMENT` -> `LOCKING` -> `FIGHTING` -> `BOSS_DEFEATED` -> `COMPLETED`.
- Boss bị giới hạn 100% trong ranh giới Boss Room: Không thể đi ra ngoài, không thể bị đẩy hay knockback ra ngoài phòng.
- Khi Boss bị tiêu diệt: Cổng sắt mở ngay lập tức, Boss rơi Vàng, Vũ khí cao cấp, Thuốc, và Cổ vật Relic trực tiếp ra sàn.

### 4.2. Hệ thống Cổ vật Relic Build & Tooltip UI
- **Flame Core**: Đòn đánh kèm thiêu đốt +8 sát thương lửa.
- **Thunder Ring**: Tăng tốc độ Dash và tỏa sóng điện.
- **Frost Heart**: Đòn đánh làm chậm 25% tốc độ của kẻ địch.
- **Blood Charm**: Máu càng thấp, sát thương tăng tối đa +50%.
- **Iron Shell**: Tăng +4 Giáp thủ, -10 Tốc độ chạy.
- **Void Crystal**: Tăng 25% cự ly Dash và giảm tiêu hao Stamina.
- Rê chuột vào icon Relic trên HUD để hiển thị Tooltip chi tiết (Tên, Rarity, Mô tả và Hiệu ứng).


---

## Assets (sprite)

- `assets/sheets/` – sprite sheet + file `.txt` mô tả tên ô (tiles, items, monsters, rogues, animals...).
- `spite/` – art gốc (demo_dungeon, boss1, boss2, hero...).
- `assets/tiles/`, `assets/bosses/` – sprite game dùng, sinh ra bởi `python tools/build_assets.py` (tile lấy từ `demo_dungeon.png`, boss thu nhỏ 0.75 → 60px / 90px).
- Phòng boss tự co giãn theo cỡ boss (`BOSS_ROOM_SIZE_BY_FLOOR` trong `settings.py`), tối thiểu 10 ô.

## Nhạc nền (BGM)

- `python tools/build_music.py` tổng hợp 3 bản loop gốc vào `assets/music/` (menu, dungeon, boss).
- Muốn dùng nhạc riêng: đặt file `.ogg/.mp3/.wav` tên `menu`, `dungeon` hoặc `boss` vào `assets/music/` (ưu tiên .ogg > .mp3 > .wav).
- Phím **N** bật/tắt nhạc, hoặc nút MUSIC trong menu Pause. Nhạc tự nhỏ lại khi pause / mở túi đồ / hiện bảng.
