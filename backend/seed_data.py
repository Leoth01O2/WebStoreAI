import os
import sys
from pathlib import Path

# Thêm backend vào sys.path để import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    getattr(sys.stderr, "reconfigure")(encoding="utf-8")

from app.core.database import get_db, get_db_transaction
from app.core.security import hash_password
from app.models.schema import init_db

def seed_database():
    print("[SEED] Khởi tạo schema database...")
    init_db()

    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Seed Users (Idempotent by username)
        users = [
            ("superadmin", hash_password("SuperAdmin@123"), "Lê Chủ Cửa Hàng", "superadmin"),
            ("admin", hash_password("Admin@123"), "Nguyễn Quản Trị", "admin"),
            ("staff", hash_password("Staff@123"), "Trần Thu Ngân", "staff"),
            ("customer", hash_password("Customer@123"), "Nguyễn Văn An (Customer)", "customer"),
            ("customer2", hash_password("Customer@123"), "Trần Thị Bình", "customer"),
        ]
        users_inserted = 0
        for u in users:
            cursor.execute("SELECT id FROM users WHERE username = ?", (u[0],))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                    u
                )
                users_inserted += 1
        if users_inserted > 0:
            print(f"[SEED] Đã tạo {users_inserted} người dùng mặc định.")

        # 2. Seed Categories (Idempotent by code)
        categories = [
            ("Âm thanh & Tai nghe", "CAT-AUDIO", "Tai nghe bluetooth, loa di động, micro thu âm"),
            ("Chuột & Bàn phím", "CAT-OFFICE", "Chuột không dây, bàn phím cơ, phụ kiện văn phòng"),
            ("Gia dụng thông minh", "CAT-SMART", "Đèn bàn bảo vệ mắt, máy hút ẩm, sạc không dây để bàn"),
            ("Phụ kiện & Dây cáp", "CAT-ACCESSORY", "Củ sạc nhanh GaN, cáp Type-C to Lightning, hub chuyển đổi"),
            ("Gaming Gear", "CAT-GAMING", "Tai nghe 7.1, lót chuột led RGB, quạt tản nhiệt laptop")
        ]
        cats_inserted = 0
        for cat in categories:
            cursor.execute("SELECT id FROM categories WHERE code = ?", (cat[1],))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO categories (name, code, description) VALUES (?, ?, ?)",
                    cat
                )
                cats_inserted += 1
        if cats_inserted > 0:
            print(f"[SEED] Đã tạo {cats_inserted} danh mục mới.")

        # Lấy map category name -> id
        cursor.execute("SELECT id, name FROM categories")
        cat_map = {row["name"]: row["id"] for row in cursor.fetchall()}

        # 3. Seed Products (25 sản phẩm đa dạng đặc tính, có cả sản phẩm hết hàng để test)
        IMAGE_MAP = {
            "SP-AUDIO-01": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&auto=format&fit=crop&q=80",
            "SP-AUDIO-02": "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=500&auto=format&fit=crop&q=80",
            "SP-AUDIO-03": "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=500&auto=format&fit=crop&q=80",
            "SP-AUDIO-04": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&auto=format&fit=crop&q=80",
            "SP-AUDIO-05": "https://images.unsplash.com/photo-1590658006821-04f4008d5717?w=500&auto=format&fit=crop&q=80",
            "SP-OFFICE-01": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=500&auto=format&fit=crop&q=80",
            "SP-OFFICE-02": "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?w=500&auto=format&fit=crop&q=80",
            "SP-OFFICE-03": "https://images.unsplash.com/photo-1511467687858-23d96c32e4ae?w=500&auto=format&fit=crop&q=80",
            "SP-OFFICE-04": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=500&auto=format&fit=crop&q=80",
            "SP-OFFICE-05": "https://images.unsplash.com/photo-1629429408209-1f912961dbd8?w=500&auto=format&fit=crop&q=80",
            "SP-SMART-01": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=500&auto=format&fit=crop&q=80",
            "SP-SMART-02": "https://images.unsplash.com/photo-1608571423902-eed4a5ad8108?w=500&auto=format&fit=crop&q=80",
            "SP-SMART-03": "https://images.unsplash.com/photo-1563861826100-9cb868fdbe1c?w=500&auto=format&fit=crop&q=80",
            "SP-SMART-04": "https://images.unsplash.com/photo-1576678927484-cc907957088c?w=500&auto=format&fit=crop&q=80",
            "SP-SMART-05": "https://images.unsplash.com/photo-1585771724684-38269d6639fd?w=500&auto=format&fit=crop&q=80",
            "SP-ACC-01": "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?w=500&auto=format&fit=crop&q=80",
            "SP-ACC-02": "https://images.unsplash.com/photo-1609592426508-cc85b13eef73?w=500&auto=format&fit=crop&q=80",
            "SP-ACC-03": "https://images.unsplash.com/photo-1625842268584-8f3296236761?w=500&auto=format&fit=crop&q=80",
            "SP-ACC-04": "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=500&auto=format&fit=crop&q=80",
            "SP-ACC-05": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&auto=format&fit=crop&q=80",
            "SP-GAME-01": "https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=500&auto=format&fit=crop&q=80",
            "SP-GAME-02": "https://images.unsplash.com/photo-1527814050087-3793815479db?w=500&auto=format&fit=crop&q=80",
            "SP-GAME-03": "https://images.unsplash.com/photo-1600080972464-8e5f35f63d08?w=500&auto=format&fit=crop&q=80",
            "SP-GAME-04": "https://images.unsplash.com/photo-1616440347437-b1c73416efc2?w=500&auto=format&fit=crop&q=80",
            "SP-GAME-05": "https://images.unsplash.com/photo-1593642702821-c8da6771f0c6?w=500&auto=format&fit=crop&q=80"
        }

        VISUAL_METADATA_MAP = {
            "SP-AUDIO-01": {
                "product_type": "headphone",
                "dominant_color": "black",
                "shape_form": "over-ear",
                "material": "plastic, faux leather, foam",
                "visible_features": '["over-ear cushions", "padded headband", "hinge folding", "control buttons"]',
                "visual_description": "Tai nghe chụp tai over-ear màu đen, đệm tai giả da mềm mại, headband có đệm, phong cách cổ điển retro tối giản",
                "search_keywords": "tai nghe, over-ear headphone, bluetooth, retro sound, black headphone, đệm tai",
            },
            "SP-AUDIO-02": {
                "product_type": "speaker",
                "dominant_color": "brown_wood",
                "shape_form": "rectangular box",
                "material": "wood, metal, fabric mesh",
                "visible_features": '["wooden enclosure", "vintage knobs", "fabric speaker grille", "metal toggle switch"]',
                "visual_description": "Loa hộp vuông vỏ gỗ màu nâu tự nhiên phong cách vintage retro, có núm xoay kim loại và màng loa bọc vải hoài cổ",
                "search_keywords": "loa bluetooth, wooden speaker, vintage box, loa go, loa retro, núm vặn",
            },
            "SP-AUDIO-03": {
                "product_type": "headphone",
                "dominant_color": "black",
                "shape_form": "over-ear studio",
                "material": "plastic, steel, acoustic foam, leather",
                "visible_features": '["large earcups", "detachable cable", "steel headband slider", "studio monitor branding"]',
                "visual_description": "Tai nghe kiểm âm studio chuyên nghiệp chụp tai màu đen, củ loa lớn 50mm, dây cáp rời bọc dù",
                "search_keywords": "tai nghe kiểm âm, studio monitor, over-ear, wired headphone, tai nghe phòng thu",
            },
            "SP-AUDIO-04": {
                "product_type": "microphone",
                "dominant_color": "black",
                "shape_form": "cylindrical desk mic",
                "material": "metal, zinc alloy",
                "visible_features": '["metal mesh grille", "shock mount", "desktop round base", "gain dial", "usb port"]',
                "visual_description": "Micro thu âm condenser để bàn hình trụ màu đen, đầu lưới kim loại, có giá chống rung shock mount và chân đế tròn",
                "search_keywords": "micro thu am, podcasting mic, usb condenser, desk mic, micro livestream",
            },
            "SP-AUDIO-05": {
                "product_type": "earbuds",
                "dominant_color": "black",
                "shape_form": "in-ear with earhook",
                "material": "silicone, plastic",
                "visible_features": '["curved ear hooks", "silicone tips", "charging contacts", "compact charging case"]',
                "visual_description": "Tai nghe không dây nhét tai thể thao có móc vành tai chống rơi rớt, đệm silicon đen mềm kháng nước",
                "search_keywords": "tai nghe the thao, sports earbuds, in-ear hook, chống nước, tai nghe chạy bộ",
            },
            "SP-OFFICE-01": {
                "product_type": "keyboard",
                "dominant_color": "white, silver",
                "shape_form": "compact tenkeyless 84 keys",
                "material": "aluminum top, ABS round keycaps",
                "visible_features": '["round typewriter keycaps", "steampunk chrome trim", "warm white led", "mechanical switches"]',
                "visual_description": "Bàn phím cơ thiết kế phím tròn cổ điển mô phỏng máy đánh chữ typewriter, viền kim loại sáng bóng, đèn nền vàng ấm",
                "search_keywords": "ban phim co, typewriter keyboard, round keycaps, retro keyboard, máy đánh chữ",
            },
            "SP-OFFICE-02": {
                "product_type": "mouse",
                "dominant_color": "dark gray",
                "shape_form": "vertical ergonomic",
                "material": "matte plastic, rubberized grip",
                "visible_features": '["vertical handshake angle", "thumb rest", "silent click buttons", "scroll wheel"]',
                "visual_description": "Chuột không dây công thái học đứng góc 57 độ màu xám đen, báng tì ngón cái êm ái, phím bấm im lặng silent",
                "search_keywords": "chuot cong thai hoc, ergonomic vertical mouse, chuot khong day, silent mouse, chống mỏi cổ tay",
            },
            "SP-OFFICE-03": {
                "product_type": "keyboard",
                "dominant_color": "space gray",
                "shape_form": "ultra-slim flat",
                "material": "aluminum alloy, chiclet keys",
                "visible_features": '["scissor switch chiclet keys", "integrated tablet cradle groove", "slim wedge profile"]',
                "visual_description": "Bàn phím không dây siêu mỏng phím chiclet gõ êm màu xám không gian, có rãnh đặt điện thoại máy tính bảng",
                "search_keywords": "ban phim khong day, slim keyboard, multi-device, chiclet keyboard, bàn phím mỏng",
            },
            "SP-OFFICE-04": {
                "product_type": "mouse",
                "dominant_color": "black",
                "shape_form": "ambidextrous symmetrical",
                "material": "matte plastic",
                "visible_features": '["symmetrical body", "rubber scroll wheel", "usb-a cable", "red optical sensor light"]',
                "visual_description": "Chuột quang có dây văn phòng đối xứng màu đen truyền thống, kích thước tiêu chuẩn, dây cáp USB",
                "search_keywords": "chuot co day, optical mouse, chuot van phong, basic wired mouse",
            },
            "SP-OFFICE-05": {
                "product_type": "desk_mat",
                "dominant_color": "brown",
                "shape_form": "large rectangular mat",
                "material": "PU leather, non-slip suede back",
                "visible_features": '["stitched edges", "leather grain texture", "waterproof surface", "90x40cm oversized"]',
                "visual_description": "Thảm trải bàn di chuột cỡ lớn 90x40cm bằng da PU màu nâu da bò cổ điển, đường chỉ may viền tỉ mỉ, chống thấm",
                "search_keywords": "lot chuot da, desk mat, pu leather pad, bàn di chuột cỡ lớn, thảm lót bàn da",
            },
            "SP-SMART-01": {
                "product_type": "lamp",
                "dominant_color": "bronze, gold",
                "shape_form": "gooseneck desk lamp",
                "material": "brass, cast iron, glass",
                "visible_features": '["exposed Edison filament bulb", "curved brass arm", "rotary dimmer switch", "heavy metal base"]',
                "visual_description": "Đèn bàn làm việc kim loại mạ đồng cổ điển, bóng đèn sợi đốt Edison lộ tim, tay đèn uốn cong thanh thoát",
                "search_keywords": "den ban, edison desk lamp, den co dien, chong can, brass lamp, đèn trang trí",
            },
            "SP-SMART-02": {
                "product_type": "diffuser",
                "dominant_color": "white, beige",
                "shape_form": "conical ceramic vase",
                "material": "ceramic, bpa-free plastic",
                "visible_features": '["ceramic textured cover", "top mist spout", "ambient bottom glow light ring", "power touch button"]',
                "visual_description": "Máy xông khuếch tán tinh dầu vỏ gốm thủ công sần màu trắng ngà thanh lịch, miệng phun sương đỉnh hình nón",
                "search_keywords": "may khuech tan tinh dau, ceramic diffuser, may xong tinh dau, vỏ gốm, phun sương siêu âm",
            },
            "SP-SMART-03": {
                "product_type": "clock",
                "dominant_color": "black, amber glow",
                "shape_form": "horizontal multi-tube",
                "material": "acrylic glass tubes, walnut base, PCB",
                "visible_features": '["6 glowing glass tubes", "exposed circuit traces", "brass buttons", "rgb backlight base"]',
                "visual_description": "Đồng hồ để bàn phong cách steampunk với 6 bóng thủy tinh phát sáng số màu cam hổ phách, đế gỗ óc chó lộ mạch",
                "search_keywords": "dong ho de ban, nixie tube clock, dong ho led, steampunk clock, đèn nixie giả lập",
            },
            "SP-SMART-04": {
                "product_type": "smart_scale",
                "dominant_color": "white",
                "shape_form": "flat square",
                "material": "tempered glass, ABS plastic, metal electrodes",
                "visible_features": '["4 round steel electrode pads", "hidden LED matrix display", "rounded glass corners"]',
                "visual_description": "Cân sức khỏe điện tử thông minh mặt kính cường lực màu trắng vuông bo tròn, có 4 điện cực kim loại đo chỉ số cơ thể",
                "search_keywords": "can dien tu, smart body scale, can suc khoe, can thong minh, kinh cuong luc",
            },
            "SP-SMART-05": {
                "product_type": "fan",
                "dominant_color": "dark green, gold trim",
                "shape_form": "cylindrical jet turbine",
                "material": "ABS plastic, metal grill, brass accents",
                "visible_features": '["circular aircraft engine cowling", "twin blades", "gold plated stand", "leather carrying handle"]',
                "visual_description": "Quạt mini để bàn hình động cơ tua-bin máy bay cổ điển màu xanh rêu phối viền kim loại vàng, có quai da xách",
                "search_keywords": "quat mini, desk fan, retro turbine fan, quat de ban, quạt vintage xanh rêu",
            },
            "SP-ACC-01": {
                "product_type": "charger",
                "dominant_color": "matte gray, black",
                "shape_form": "cube robot figurine",
                "material": "flame-retardant PC, silicone boots",
                "visible_features": '["robot face with LED eyes screen", "removable magnetic shoe boots", "2 USB-C 1 USB-A ports on top"]',
                "visual_description": "Củ sạc nhanh công nghệ GaN hình chú robot tí hon màu xám mờ, màn hình hiển thị biểu cảm mắt LED vui nhộn",
                "search_keywords": "cu sac nhanh, gan charger 65w, retro robot charger, củ sạc hình robot, sạc type c",
            },
            "SP-ACC-02": {
                "product_type": "cable",
                "dominant_color": "black, silver",
                "shape_form": "braided cord",
                "material": "nylon braided fiber, zinc alloy connectors",
                "visible_features": '["tightly braided black jacket", "reinforced strain relief collars", "metal housing plugs", "e-marker chip"]',
                "visual_description": "Dây cáp sạc và truyền dữ liệu bọc sợi dù xoắn màu đen siêu bền, 2 đầu cắm bọc hợp kim kẽm bạc chống gãy gập",
                "search_keywords": "cap sac type c, braided cable 100w, day sac boc du, cáp kim loại siêu bền",
            },
            "SP-ACC-03": {
                "product_type": "hub_adapter",
                "dominant_color": "space gray",
                "shape_form": "rectangular dongle bar",
                "material": "anodized aluminum",
                "visible_features": '["integrated short braided type-c pigtail", "side ports array hdmi sd tf usb", "aluminum chassis"]',
                "visual_description": "Bộ chia cổng Hub Type-C 6 trong 1 vỏ nhôm anodized màu xám space gray, kèm dây nối bọc dù ngắn",
                "search_keywords": "hub type c, adapter 6 in 1, cong chuyen doi hdmi, usb c hub, vỏ nhôm tản nhiệt",
            },
            "SP-ACC-04": {
                "product_type": "power_bank",
                "dominant_color": "transparent, black, yellow accents",
                "shape_form": "thick rectangular prism",
                "material": "transparent polycarbonate, aluminum alloy",
                "visible_features": '["see-through clear casing", "exposed circuit board", "color digital battery display", "dual usb ports"]',
                "visual_description": "Pin sạc dự phòng vỏ nhựa trong suốt lộ toàn bộ bo mạch điện tử phong cách cyberpunk công nghệ, màn hình hiển thị LED",
                "search_keywords": "pin sac du phong, power bank 20000mah, cyberpunk transparent, sạc dự phòng trong suốt",
            },
            "SP-ACC-05": {
                "product_type": "laptop_stand",
                "dominant_color": "silver",
                "shape_form": "dual-arm folding stand",
                "material": "solid aluminum alloy, silicone anti-slip pads",
                "visible_features": '["round 360 rotating base", "twin articulated riser arms", "ventilation cutout plate", "silicone hooks"]',
                "visual_description": "Giá đỡ nâng máy tính xách tay bằng hợp kim nhôm màu bạc sáng, trục xoay 360 độ kèm khớp gập kép tùy chỉnh độ cao",
                "search_keywords": "gia do laptop, aluminum laptop stand, ke tan nhiet, xoay 360 do, chân đế máy tính",
            },
            "SP-GAME-01": {
                "product_type": "headphone",
                "dominant_color": "black, red rgb",
                "shape_form": "bulky gaming over-ear",
                "material": "rugged ABS, breathable mesh fabric earpads",
                "visible_features": '["external rotating boom microphone", "glowing red RGB earcups", "thick suspension headband cushion"]',
                "visual_description": "Tai nghe gaming chụp tai cỡ lớn phong cách hầm hố màu đen, viền đèn LED đỏ rực rỡ, tích hợp micro boom dài",
                "search_keywords": "tai nghe gaming, gaming headset 7.1, tai nghe chup tai game, led rgb, bass rung",
            },
            "SP-GAME-02": {
                "product_type": "mouse",
                "dominant_color": "white",
                "shape_form": "ergonomic ultralight claw",
                "material": "lightweight composite plastic, PTFE feet",
                "visible_features": '["solid lightweight matte shell", "side textured grip grooves", "white scroll wheel", "pure PTFE glide skates"]',
                "visual_description": "Chuột chơi game không dây siêu nhẹ chỉ 55g màu trắng tuyết bề mặt nhám mịn, thiết kế công thái học tối giản",
                "search_keywords": "chuot gaming, ultralight wireless mouse 55g, chuot trang sieu nhe, sensor 26000 dpi",
            },
            "SP-GAME-03": {
                "product_type": "game_controller",
                "dominant_color": "black, dark purple accents",
                "shape_form": "ergonomic console gamepad",
                "material": "textured plastic, rubberized grips",
                "visible_features": '["dual analog thumbsticks", "d-pad", "four face buttons abxy", "analog triggers", "center led logo"]',
                "visual_description": "Tay cầm chơi game gamepad không dây màu đen nhám cầm nắm đầm tay, cần analog chống trôi Hall Effect và phím nẩy",
                "search_keywords": "tay cam choi game, wireless gamepad, hall effect controller, tay cầm pc switch, joystick",
            },
            "SP-GAME-04": {
                "product_type": "mousepad",
                "dominant_color": "black, multi-color rgb border",
                "shape_form": "extended wide rectangular pad",
                "material": "micro-textured cloth, non-slip rubber base, optic fiber tube",
                "visible_features": '["illuminated RGB perimeter border", "control switch box in corner", "smooth fabric surface", "80x30cm"]',
                "visual_description": "Tấm lót chuột cỡ dài 80x30cm phủ bàn màu đen, viền phát quang dải LED RGB đổi 14 chế độ màu sặc sỡ",
                "search_keywords": "tam lot chuot led, rgb mousepad, ban di chuot gaming, lot chuot co lon",
            },
            "SP-GAME-05": {
                "product_type": "cooling_pad",
                "dominant_color": "black, blue led",
                "shape_form": "angled cooling stand",
                "material": "metal mesh top, reinforced plastic frame",
                "visible_features": '["6 illuminated blue LED fans", "full metal top mesh", "front anti-slip baffles", "rear control panel"]',
                "visual_description": "Đế tản nhiệt laptop bề mặt lưới kim loại đen có 6 quạt làm mát phát sáng đèn LED xanh dương, chân chống trượt",
                "search_keywords": "de tan nhiet laptop, laptop cooling pad, 6 quat led xanh, de lam mat may tinh",
            }
        }

        # 3. Seed Products (Idempotent by sku)
        products = [
            # Âm thanh
            ("SP-AUDIO-01", "Tai nghe Bluetooth RetroSound A1", cat_map["Âm thanh & Tai nghe"], 220000, 350000, 24, 5, "chiếc", "active", IMAGE_MAP["SP-AUDIO-01"], "Tai nghe không dây pin 20 giờ, chống ồn chủ động ANC nhẹ, chất âm hoài niệm ấm áp, kết nối Bluetooth 5.3."),
            ("SP-AUDIO-02", "Loa Bluetooth Gỗ Vintage Box", cat_map["Âm thanh & Tai nghe"], 450000, 690000, 15, 3, "chiếc", "active", IMAGE_MAP["SP-AUDIO-02"], "Loa vỏ gỗ tự nhiên phong cách retro thập niên 90, công suất 20W, pin 12 giờ, tích hợp đài FM và cổng AUX."),
            ("SP-AUDIO-03", "Tai nghe chụp tai Monitor Studio Pro", cat_map["Âm thanh & Tai nghe"], 800000, 1250000, 8, 2, "chiếc", "active", IMAGE_MAP["SP-AUDIO-03"], "Tai nghe kiểm âm chụp tai có dây tháo rời, màng loa 50mm, âm thanh trung thực chi tiết cho phòng thu."),
            ("SP-AUDIO-04", "Micro Thu Âm Podcasting USB M1", cat_map["Âm thanh & Tai nghe"], 550000, 890000, 10, 3, "chiếc", "active", IMAGE_MAP["SP-AUDIO-04"], "Micro condenser cắm cổng USB, chống rung kim loại, lọc tạp âm tốt, phù hợp livestream và họp trực tuyến."),
            ("SP-AUDIO-05", "Tai nghe Earbuds Thể Thao RunFree", cat_map["Âm thanh & Tai nghe"], 180000, 290000, 0, 5, "chiếc", "active", IMAGE_MAP["SP-AUDIO-05"], "Tai nghe nhét tai kháng nước IPX7, đệm silicon chống rơi khi chạy bộ (TẠM HẾT HÀNG để kiểm tra guard)."),

            # Chuột & Phím
            ("SP-OFFICE-01", "Bàn phím cơ Retro Typewriter T80", cat_map["Chuột & Bàn phím"], 650000, 990000, 18, 4, "chiếc", "active", IMAGE_MAP["SP-OFFICE-01"], "Bàn phím cơ layout 84 phím mô phỏng máy đánh chữ cổ điển, switch Blue tactile gõ giòn, đèn LED vàng ấm."),
            ("SP-OFFICE-02", "Chuột không dây Công thái học Silent M3", cat_map["Chuột & Bàn phím"], 190000, 320000, 30, 5, "chiếc", "active", IMAGE_MAP["SP-OFFICE-02"], "Chuột cầm dọc chống mỏi cổ tay, nút bấm êm tuyệt đối không gây ồn, pin sạc Type-C dùng 40 ngày."),
            ("SP-OFFICE-03", "Bàn phím không dây Slim Multi-Device", cat_map["Chuột & Bàn phím"], 280000, 450000, 12, 3, "chiếc", "active", IMAGE_MAP["SP-OFFICE-03"], "Bàn phím siêu mỏng kết nối cùng lúc 3 thiết bị máy tính, máy tính bảng, điện thoại qua Bluetooth và 2.4G."),
            ("SP-OFFICE-04", "Chuột quang có dây Văn phòng Basic", cat_map["Chuột & Bàn phím"], 45000, 85000, 45, 10, "chiếc", "active", IMAGE_MAP["SP-OFFICE-04"], "Chuột có dây bền bỉ, cắm là chạy, độ phân giải 1200 DPI, phù hợp sử dụng công ty và học sinh."),
            ("SP-OFFICE-05", "Bàn di chuột Da PU Cỡ lớn 90x40cm", cat_map["Chuột & Bàn phím"], 80000, 145000, 22, 5, "chiếc", "active", IMAGE_MAP["SP-OFFICE-05"], "Thảm lót bàn làm việc da cao cấp chống thấm nước, êm ái, màu nâu da bò phong cách vintage."),

            # Gia dụng thông minh
            ("SP-SMART-01", "Đèn bàn LED Cổ điển Chống cận Edison", cat_map["Gia dụng thông minh"], 320000, 490000, 14, 3, "chiếc", "active", IMAGE_MAP["SP-SMART-01"], "Đèn bàn thân kim loại mạ đồng, bóng LED ánh sáng vàng bảo vệ mắt, có nút vặn chiết áp điều chỉnh độ sáng."),
            ("SP-SMART-02", "Máy khuếch tán tinh dầu gốm Ceramic", cat_map["Gia dụng thông minh"], 210000, 350000, 16, 4, "chiếc", "active", IMAGE_MAP["SP-SMART-02"], "Máy xông tinh dầu công nghệ siêu âm phun sương mịn, vỏ gốm thủ công hoài cổ, dung tích 300ml, tự ngắt khi hết nước."),
            ("SP-SMART-03", "Đồng hồ LED để bàn Giả lập Đèn Nixie", cat_map["Gia dụng thông minh"], 750000, 1190000, 5, 2, "chiếc", "active", IMAGE_MAP["SP-SMART-03"], "Đồng hồ retro-futuristic ống thủy tinh phát quang phong cách steampunk, hiển thị giờ, thời tiết và RGB."),
            ("SP-SMART-04", "Cân điện tử thông minh đo 12 chỉ số", cat_map["Gia dụng thông minh"], 150000, 260000, 20, 5, "chiếc", "active", IMAGE_MAP["SP-SMART-04"], "Mặt kính cường lực, kết nối app điện thoại qua bluetooth theo dõi cân nặng, lượng mỡ, cơ bắp."),
            ("SP-SMART-05", "Quạt mini để bàn Retro Turbine", cat_map["Gia dụng thông minh"], 110000, 195000, 25, 5, "chiếc", "active", IMAGE_MAP["SP-SMART-05"], "Quạt sạc pin USB hình động cơ máy bay cổ điển, 3 tốc độ gió, chạy êm ái mát mẻ."),

            # Phụ kiện & Cáp
            ("SP-ACC-01", "Củ sạc nhanh GaN 65W Retro Robot", cat_map["Phụ kiện & Dây cáp"], 290000, 480000, 35, 5, "chiếc", "active", IMAGE_MAP["SP-ACC-01"], "Củ sạc 3 cổng (2 Type-C, 1 USB-A) hình robot cổ điển có mắt LED biểu thị công suất sạc, hỗ trợ laptop và iPhone."),
            ("SP-ACC-02", "Cáp sạc Bọc dù Kim loại Siêu bền Type-C 100W", cat_map["Phụ kiện & Dây cáp"], 60000, 110000, 50, 10, "sợi", "active", IMAGE_MAP["SP-ACC-02"], "Dây cáp sạc bọc vải dù chịu lực, đầu hợp kim kẽm chống gãy gập, truyền dữ liệu 480Mbps."),
            ("SP-ACC-03", "Hub chuyển đổi 6 trong 1 Type-C sang HDMI 4K", cat_map["Phụ kiện & Dây cáp"], 250000, 420000, 19, 4, "chiếc", "active", IMAGE_MAP["SP-ACC-03"], "Vỏ nhôm tản nhiệt tốt, cổng HDMI 4K@60Hz, 3 cổng USB 3.0, khe thẻ nhớ SD/TF và sạc PD 100W."),
            ("SP-ACC-04", "Pin sạc dự phòng Trong suốt Cyberpunk 20000mAh", cat_map["Phụ kiện & Dây cáp"], 380000, 590000, 12, 3, "chiếc", "active", IMAGE_MAP["SP-ACC-04"], "Pin sạc dự phòng lộ bảng mạch retro công nghệ, sạc nhanh 22.5W, màn hình LCD hiển thị phần trăm chính xác."),
            ("SP-ACC-05", "Giá đỡ laptop Hợp kim nhôm Xoay 360 độ", cat_map["Phụ kiện & Dây cáp"], 180000, 290000, 15, 3, "chiếc", "active", IMAGE_MAP["SP-ACC-05"], "Chân đế nâng hạ độ cao công thái học, xoay 360 độ có tiếng click cơ học cực sướng tai."),

            # Gaming Gear
            ("SP-GAME-01", "Tai nghe Gaming 7.1 Rung Bass G200", cat_map["Gaming Gear"], 380000, 590000, 11, 3, "chiếc", "active", IMAGE_MAP["SP-GAME-01"], "Tai nghe âm thanh vòm 7.1 có động cơ rung chân thực theo tiếng nổ, mic lọc tiếng ồn, đệm tai êm ái."),
            ("SP-GAME-02", "Chuột Gaming Không dây Siêu nhẹ 55g", cat_map["Gaming Gear"], 420000, 680000, 14, 4, "chiếc", "active", IMAGE_MAP["SP-GAME-02"], "Cảm biến quang học 26000 DPI, kết nối không dây 1000Hz không độ trễ, trọng lượng siêu nhẹ 55 gram."),
            ("SP-GAME-03", "Tay cầm chơi game Không dây Hall Effect H1", cat_map["Gaming Gear"], 460000, 750000, 9, 3, "chiếc", "active", IMAGE_MAP["SP-GAME-03"], "Cần joystick từ tính chống trôi vĩnh viễn, hỗ trợ PC, Nintendo Switch, điện thoại Android/iOS."),
            ("SP-GAME-04", "Tấm lót chuột Led RGB Cỡ cực đại", cat_map["Gaming Gear"], 120000, 210000, 18, 5, "chiếc", "active", IMAGE_MAP["SP-GAME-04"], "Bề mặt vải speed mượt mà, viền LED RGB 14 chế độ phát sáng, kích thước 80x30cm chống trượt."),
            ("SP-GAME-05", "Đế tản nhiệt Laptop Gaming 6 quạt mạnh mẽ", cat_map["Gaming Gear"], 190000, 310000, 0, 4, "chiếc", "active", IMAGE_MAP["SP-GAME-05"], "Đế làm mát có màn hình LED điều chỉnh tốc độ, 6 quạt gió cực mát (TẠM HẾT HÀNG để test).")
        ]
        prods_inserted = 0
        for prod in products:
            cursor.execute("SELECT id FROM products WHERE sku = ?", (prod[0],))
            if not cursor.fetchone():
                cursor.execute(
                    """INSERT INTO products (
                        sku, name, category_id, cost_price, selling_price,
                        stock_quantity, min_stock_alert, unit, status, image_url, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    prod
                )
                prods_inserted += 1
        if prods_inserted > 0:
            print(f"[SEED] Đã tạo {prods_inserted} sản phẩm mới.")

        # Cập nhật ảnh cho các sản phẩm hiện có nếu còn trống
        for sku, img_url in IMAGE_MAP.items():
            cursor.execute(
                "UPDATE products SET image_url = ? WHERE sku = ? AND (image_url IS NULL OR image_url = '')",
                (img_url, sku)
            )

        # 4. Seed Customers (Idempotent by customer_code)
        customers = [
            ("KH-001", "Nguyễn Văn An", "0987654321", "an.nguyen@example.com", "Số 12 Phố Cổ, Hoàn Kiếm, Hà Nội", "vip", 4850000),
            ("KH-002", "Trần Thị Bình", "0912345678", "binh.tran@example.com", "45 Nguyễn Trãi, Quận 1, TP.HCM", "retail", 850000),
            ("KH-003", "Lê Hoàng Long", "0934567890", "long.le@example.com", "Tòa nhà FPT, Cầu Giấy, Hà Nội", "wholesale", 12500000),
            ("KH-004", "Phạm Minh Đức", "0978901234", "duc.pham@example.com", "88 Lê Duẩn, Hải Châu, Đà Nẵng", "retail", 320000),
            ("KH-005", "Vũ Thu Trang", "0905123456", "trang.vu@example.com", "15 Phan Chu Trinh, Vũng Tàu", "vip", 3200000)
        ]
        custs_inserted = 0
        for cust in customers:
            cursor.execute("SELECT id FROM customers WHERE customer_code = ?", (cust[0],))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO customers (customer_code, name, phone, email, address, group_name, total_spent) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    cust
                )
                custs_inserted += 1
        if custs_inserted > 0:
            print(f"[SEED] Đã tạo {custs_inserted} khách hàng mới.")

        # Liên kết tài khoản customer với hồ sơ khách hàng (Customer Role RBAC)
        cursor.execute("SELECT id FROM users WHERE username = 'customer'")
        u_cust = cursor.fetchone()
        if u_cust:
            cursor.execute("UPDATE customers SET user_id = ? WHERE customer_code = 'KH-001' AND (user_id IS NULL OR user_id != ?)", (u_cust["id"], u_cust["id"]))

        cursor.execute("SELECT id FROM users WHERE username = 'customer2'")
        u_cust2 = cursor.fetchone()
        if u_cust2:
            cursor.execute("UPDATE customers SET user_id = ? WHERE customer_code = 'KH-002' AND (user_id IS NULL OR user_id != ?)", (u_cust2["id"], u_cust2["id"]))

        # 5. Seed Sample Orders & Inventory Logs (Idempotent by order_code and receipt_code)
        # Hóa đơn 1 (Đã hoàn tất)
        cursor.execute("SELECT id FROM orders WHERE order_code = 'HD-20260901-001'")
        if not cursor.fetchone():
            cursor.execute("SELECT id, selling_price, stock_quantity FROM products WHERE sku = 'SP-AUDIO-01'")
            sp1 = cursor.fetchone()
            cursor.execute("SELECT id, selling_price, stock_quantity FROM products WHERE sku = 'SP-OFFICE-01'")
            sp2 = cursor.fetchone()
            if sp1 and sp2:
                cursor.execute(
                    """INSERT INTO orders (order_code, customer_id, user_id, total_amount, discount_amount, final_amount, payment_method, status, note, created_at)
                       VALUES ('HD-20260901-001', 1, 2, 1340000, 40000, 1300000, 'transfer', 'completed', 'Khách VIP mua trực tiếp', datetime('now', '-2 days'))"""
                )
                order1_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)",
                    (order1_id, sp1["id"], 1, 350000, 350000)
                )
                cursor.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)",
                    (order1_id, sp2["id"], 1, 990000, 990000)
                )
                cursor.execute(
                    "INSERT INTO inventory_logs (product_id, change_type, reference_code, quantity_before, change_quantity, quantity_after, note, created_at) VALUES (?, 'sale', 'HD-20260901-001', ?, -1, ?, 'Bán hàng cho khách VIP', datetime('now', '-2 days'))",
                    (sp1["id"], sp1["stock_quantity"] + 1, sp1["stock_quantity"])
                )

        # Hóa đơn 2 (Đã hoàn tất hôm nay)
        cursor.execute("SELECT id FROM orders WHERE order_code = 'HD-20260903-002'")
        if not cursor.fetchone():
            cursor.execute("SELECT id, selling_price, stock_quantity FROM products WHERE sku = 'SP-ACC-01'")
            sp3 = cursor.fetchone()
            if sp3:
                cursor.execute(
                    """INSERT INTO orders (order_code, customer_id, user_id, total_amount, discount_amount, final_amount, payment_method, status, note, created_at)
                       VALUES ('HD-20260903-002', 2, 2, 480000, 0, 480000, 'cash', 'completed', 'Khách lẻ thanh toán tiền mặt', datetime('now', '-2 hours'))"""
                )
                order2_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)",
                    (order2_id, sp3["id"], 1, 480000, 480000)
                )

        # Phiếu nhập hàng ban đầu (Purchase Receipt)
        cursor.execute("SELECT id FROM purchase_receipts WHERE receipt_code = 'PN-20260901-001'")
        if not cursor.fetchone():
            cursor.execute(
                """INSERT INTO purchase_receipts (receipt_code, supplier_name, user_id, total_amount, status, note)
                   VALUES ('PN-20260901-001', 'Tổng kho Phụ kiện DigiTech Sài Gòn', 1, 15000000, 'completed', 'Nhập lô hàng đầu tháng 9')"""
            )

        # 6. Seed Product Visual Metadata (Phase 12B)
        cursor.execute("SELECT id, sku, image_url FROM products")
        prod_rows = cursor.fetchall()
        meta_count = 0
        for prod in prod_rows:
            sku = prod["sku"]
            if sku in VISUAL_METADATA_MAP:
                cursor.execute("SELECT id FROM product_visual_metadata WHERE product_id = ?", (prod["id"],))
                if not cursor.fetchone():
                    meta = VISUAL_METADATA_MAP[sku]
                    img_path = prod["image_url"] or meta.get("image_path", "")
                    cursor.execute(
                        """INSERT INTO product_visual_metadata (
                            product_id, image_path, product_type, dominant_color,
                            shape_form, material, visible_features, visual_description,
                            search_keywords
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            prod["id"],
                            img_path,
                            meta["product_type"],
                            meta.get("dominant_color"),
                            meta.get("shape_form"),
                            meta.get("material"),
                            meta.get("visible_features"),
                            meta.get("visual_description"),
                            meta.get("search_keywords")
                        )
                    )
                    meta_count += 1
        if meta_count > 0:
            print(f"[SEED] Đã nạp thành công visual metadata cho {meta_count} sản phẩm.")

        conn.commit()

    print("[SEED] Hoàn tất nạp dữ liệu mẫu cho StoreFlow AI!")

if __name__ == "__main__":
    seed_database()
