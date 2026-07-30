import csv, time, random, os, glob
from PIL import Image
from playwright.sync_api import sync_playwright

profile_path = os.path.join(os.getcwd(), "whatsapp_profile")
profile_exists = os.path.isdir(profile_path) and len(os.listdir(profile_path)) > 0

WATCH_DIR = os.getcwd()          # folder to watch for .csv files
POLL_SECONDS = 20


def normalize_image(path, min_size=800):
    """Resize small images so they render as normal photos, not sticker-style."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if max(w, h) < min_size:
        scale = min_size / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)))
    out_path = os.path.splitext(path)[0] + "_normalized.jpg"
    img.save(out_path, "JPEG", quality=95)
    return out_path


with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        profile_path,
        headless=False,
    )
    page = context.new_page()
    page.goto("https://web.whatsapp.com")

    if profile_exists:
        try:
            page.wait_for_selector('div[aria-label="Chat list"], #pane-side', timeout=20000)
            print("Existing session detected, skipping QR wait.")
        except Exception:
            print("Session may have expired — please scan QR if prompted.")
            input("Scan QR if needed, then press Enter...")
    else:
        input("Scan QR if needed, then press Enter...")

    def get_active_textbox(timeout=15000):
        boxes = page.locator('div[contenteditable="true"][role="textbox"]')
        boxes.first.wait_for(state="attached", timeout=timeout)

        deadline = time.time() + (timeout / 1000)
        while time.time() < deadline:
            count = boxes.count()
            for i in range(count):
                candidate = boxes.nth(i)
                if candidate.is_visible():
                    return candidate
            time.sleep(0.2)

        raise Exception("No visible textbox found")

    def clear_and_type(box, text):
        box.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        box.type(text)

    def open_chat_via_search(phone):
        search_box = page.locator('input[aria-label="Search or start a new chat"]')
        if search_box.count() == 0:
            return False

        search_box.first.click()
        search_box.first.fill("")
        search_box.first.type(phone)
        time.sleep(0.8)

        result = page.locator(f'span[title]:has-text("{phone}")').first
        if result.count() == 0:
            page.keyboard.press("Escape")
            search_box.first.fill("")
            return False

        result.click()
        page.keyboard.press("Escape")

        try:
            get_active_textbox()
        except Exception:
            return False
        return True

    def open_chat_via_reload(phone):
        page.goto(f"https://web.whatsapp.com/send?phone={phone}")
        page.wait_for_load_state("networkidle", timeout=20000)

        if page.locator('text=Phone number shared via url is invalid').count() > 0:
            raise Exception(f"Invalid WhatsApp number: {phone}")

        continue_btn = page.locator('text=Continue to Chat')
        if continue_btn.count() > 0:
            continue_btn.click()
            page.wait_for_load_state("networkidle", timeout=20000)

        spinner = page.locator('div[role="progressbar"]')
        if spinner.count() > 0:
            try:
                spinner.first.wait_for(state="hidden", timeout=20000)
            except Exception:
                pass

        get_active_textbox()

    def open_chat(phone):
        if open_chat_via_search(phone):
            return
        open_chat_via_reload(phone)

    def click_visible_send_button(caption_box):
        all_send_btns = page.locator('button:has(span[data-testid="wds-ic-send-filled"])')
        send_btn = None
        for i in range(all_send_btns.count()):
            candidate = all_send_btns.nth(i)
            if candidate.is_visible():
                send_btn = candidate
                break

        if send_btn:
            send_btn.click()
        else:
            caption_box.click()
            caption_box.press("Enter")

    def send_text(message):
        box = get_active_textbox()
        clear_and_type(box, message)
        box.press("Enter")

    def send_file_with_caption(path, caption=None):
        is_doc = not path.lower().endswith((".jpg", ".jpeg", ".png", ".mp4"))
        if not is_doc and not path.lower().endswith(".mp4"):
            path = normalize_image(path)

        attach_btn = page.locator(
            'button[title="Attach"], div[title="Attach"], span[data-icon="plus-rounded"]'
        ).first
        attach_btn.wait_for(state="visible", timeout=10000)
        attach_btn.click()

        menu_label = "Document" if is_doc else "Photos & videos"
        menu_item = page.get_by_text(menu_label, exact=True)
        menu_item.wait_for(state="visible", timeout=5000)

        with page.expect_file_chooser() as fc_info:
            menu_item.click()
        file_chooser = fc_info.value
        file_chooser.set_files(os.path.abspath(path))

        preview_caption_box = page.locator(
            'div[contenteditable="true"][aria-placeholder="Add a caption"], '
            'div[contenteditable="true"][data-testid="media-caption-input"]'
        )
        try:
            preview_caption_box.first.wait_for(state="visible", timeout=15000)
            caption_box = preview_caption_box.first
        except Exception:
            caption_box = get_active_textbox()

        if caption:
            clear_and_type(caption_box, caption)

        click_visible_send_button(caption_box)
        time.sleep(1.5)

    def process_entry(phone, message, file_path):
        try:
            open_chat(phone)
            print(f"Chat opened: {phone}")

            if file_path:
                send_file_with_caption(file_path, caption=message if message else None)
                print(f"File+caption sent to {phone}")
            elif message:
                send_text(message)
                print(f"Text sent to {phone}")
            else:
                print(f"Nothing to send for {phone} (empty row)")

            time.sleep(random.uniform(3, 6))
        except Exception as e:
            print(f"FAILED for {phone}: {e}")

    def process_csv_file(csv_path):
        print(f"\nProcessing CSV: {csv_path}")
        try:
            with open(csv_path, encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
        except Exception as e:
            print(f"Could not read {csv_path}: {e}")
            return

        for row in rows:
            phone = row.get("phone", "").strip()
            message = row.get("message", "").strip()
            file_path = row.get("file_path", "").strip()

            if not phone:
                continue

            process_entry(phone, message, file_path)

        print(f"Finished processing: {csv_path}")

    # ---------------- FOLDER WATCH LOOP ----------------
    print(f"\nWatching '{WATCH_DIR}' for .csv files every {POLL_SECONDS}s.")
    print("Each .csv found is fully processed, then deleted, so only new uploads get sent.")
    print("Press Ctrl+C to stop and close the browser.\n")

    try:
        while True:
            csv_files = glob.glob(os.path.join(WATCH_DIR, "*.csv"))

            for csv_path in csv_files:
                process_csv_file(csv_path)

                try:
                    os.remove(csv_path)
                    print(f"Deleted {os.path.basename(csv_path)} after sending.")
                except Exception as e:
                    print(f"Could not delete {csv_path}: {e}")

            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopping watch loop...")

    context.close()
    print("Browser closed.")