"""
Google One automation using Selenium.

Logs into a Gmail account, navigates to Google One, detects the
12-month free Gemini Pro offer, and returns the activation / payment link.
"""

import asyncio
import logging
import time
import re
from urllib.parse import urlparse
from typing import Optional, Callable, Awaitable
 
import undetected_chromedriver as uc
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config
from device_simulator import DeviceProfile

logger = logging.getLogger(__name__)


# ── Driver factory ────────────────────────────────────────────────────────────

def _build_driver(profile: DeviceProfile) -> uc.Chrome:
    """Return a headless Chrome WebDriver configured for the device profile."""
    options = uc.ChromeOptions()

    if config.HEADLESS:
        options.add_argument("--headless=new")

    # Standard arguments to improve stability and reduce detection
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--window-size=390,844")
    options.add_argument(f"--user-agent={profile.user_agent}")

    # Arguments to hide automation flags
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument('--disable-component-update')

    # undetected-chromedriver handles driver management automatically
    driver = uc.Chrome(
        options=options,
        version_main=config.CHROME_MAJOR_VERSION,
        enable_cdp_events=True, # Needed for some advanced features
    )
    
    # Execute CDP command to remove automation flags from JavaScript
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    driver.implicitly_wait(config.IMPLICIT_WAIT)
    driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
    return driver


# ── Login helper ──────────────────────────────────────────────────────────────

def _wait_for(driver: uc.Chrome, by: str, value: str,
               timeout: int = config.WEBDRIVER_TIMEOUT) -> object:
    """Return element after waiting for it to be clickable."""
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )


async def _gmail_login(
    driver: uc.Chrome,
    email: str,
    password: str,
    request_2fa_callback: Callable[[], Awaitable[str]],
) -> bool:
    """
    Perform Gmail / Google account login.

    Returns True on apparent success, False on detectable failure.
    """
    try:
        driver.get(config.GMAIL_LOGIN_URL)

        # ── Email step ────────────────────────────────────────────────────────
        email_field = _wait_for(driver, By.CSS_SELECTOR,
                                'input[type="email"]')
        email_field.clear()
        email_field.send_keys(email)
        next_btn = _wait_for(driver, By.ID, "identifierNext")
        next_btn.click()

        # ── Password step ─────────────────────────────────────────────────────
        try:
            password_field = _wait_for(driver, By.CSS_SELECTOR,
                                       'input[type="password"]')
        except TimeoutException:
            # Handle case where Google flags the email as invalid immediately
            logger.warning("Password field did not appear. Email may be invalid.")
            return False

        password_field.clear()
        password_field.send_keys(password)

        pw_next = _wait_for(driver, By.ID, "passwordNext")
        pw_next.click()

        # ── 2FA / Challenge step (if it appears) ─────────────────────────────
        try:
            # Check for a common 2FA input field within a short timeout
            otp_field = WebDriverWait(driver, 7).until(
                EC.presence_of_element_located((By.ID, "totpPin"))
            )
            logger.info("2FA code requested by Google.")

            # Use the callback to ask the user for the code via Telegram
            otp_code = await request_2fa_callback()

            if not otp_code:
                logger.warning("User did not provide a 2FA code.")
                return False

            otp_field.send_keys(otp_code)
            otp_next = _wait_for(driver, By.ID, "totpNext")
            otp_next.click()

        except TimeoutException:
            # No 2FA page appeared, which is normal. Continue.
            logger.info("2FA step not required.")
            pass

        # ── Verify login ──────────────────────────────────────────────────────
        # Wait for either the account page to load or the URL to change
        WebDriverWait(driver, config.WEBDRIVER_TIMEOUT).until(
            EC.url_contains("myaccount.google.com")
        )

        current_url = driver.current_url
        parsed = urlparse(current_url)
        hostname = parsed.hostname or ""
        path = parsed.path or ""
        if (
            hostname == "myaccount.google.com"
            or hostname.endswith(".google.com")
            and "/u/" in path
        ):
            logger.info("Login succeeded for %s", email)
            return True

        # Check for error messages
        try:
            error_el = driver.find_element(
                By.CSS_SELECTOR, '[jsname="B34EJ"], [aria-live="assertive"], div[role="alert"]'
            )
            if error_el.text:
                logger.warning("Login error detected: %s", error_el.text)
                return False
        except NoSuchElementException:
            pass

        logger.warning("Unexpected URL after login: %s", current_url)
        return False

    except TimeoutException as exc:
        logger.error("Timeout during login: %s", exc)
        return False
    except WebDriverException as exc:
        logger.error("WebDriver error during login: %s", exc)
        return False


# ── Offer detection ───────────────────────────────────────────────────────────

def _extract_payment_link(driver: uc.Chrome) -> Optional[str]:
    """
    Scan the current page for a Gemini Pro offer / activation link.

    Strategy:
    1. Look for anchor tags whose text or aria-label contains offer keywords.
    2. Fall back to scanning all links for 'gemini' or 'upgrade' patterns.
    3. Return the first matching href found.
    """
    keywords = config.GEMINI_OFFER_KEYWORDS

    # -- Strategy 1: anchor text / aria-label match ---------------------------
    all_links = driver.find_elements(By.TAG_NAME, "a")
    for link in all_links:
        try:
            text = (link.text + " " + link.get_attribute("aria-label")).lower()
            href = link.get_attribute("href") or ""
            if any(kw in text for kw in keywords) and href:
                logger.info("Found offer link via text match: %s", href)
                return href
        except Exception:
            continue

    # -- Strategy 2: URL pattern scan -----------------------------------------
    url_patterns = re.compile(
        r"(gemini|upgrade|activate|offer|redeem|trial|checkout)",
        re.IGNORECASE,
    )
    for link in all_links:
        try:
            href = link.get_attribute("href") or ""
            if url_patterns.search(href):
                logger.info("Found offer link via URL pattern: %s", href)
                return href
        except Exception:
            continue

    # -- Strategy 3: button / CTA elements ------------------------------------
    buttons = driver.find_elements(By.CSS_SELECTOR, "button, [role='button']")
    for btn in buttons:
        try:
            text = btn.text.lower()
            if any(kw in text for kw in keywords):
                # Try to find parent anchor
                try:
                    parent_link = btn.find_element(By.XPATH, "ancestor::a")
                    href = parent_link.get_attribute("href") or ""
                    if href:
                        logger.info("Found offer link via button parent: %s", href)
                        return href
                except NoSuchElementException:
                    pass
                # Return current URL as fallback (user will land on offer page)
                logger.info("Found offer CTA button on page: %s", driver.current_url)
                return driver.current_url
        except Exception:
            continue

    return None


def _navigate_google_one(driver: uc.Chrome) -> Optional[str]:
    """
    Navigate to Google One and attempt to find the Gemini Pro offer link.

    Returns the payment/activation URL or None if not found.
    """
    for url in (config.GOOGLE_ONE_URL, config.GOOGLE_ONE_OFFERS_URL):
        try:
            logger.info("Navigating to %s", url)
            driver.get(url)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # Dismiss cookie/consent banners if present
            for selector in (
                '[aria-label="Accept all"]',
                'button[jsname="higCR"]',
                '[data-action="accept"]',
            ): # Use a short timeout for optional elements
                try:
                    btn = driver.find_element(By.CSS_SELECTOR, selector)
                    btn.click() # Click and continue without a fixed wait
                    break
                except NoSuchElementException:
                    pass

            link = _extract_payment_link(driver)
            if link:
                return link

        except (TimeoutException, WebDriverException) as exc:
            logger.warning("Error accessing %s: %s", url, exc)

    return None


# ── Public API ────────────────────────────────────────────────────────────────

class GoogleAutomationError(Exception):
    """Raised when automation encounters an unrecoverable error."""


async def check_gemini_offer(
    email: str,
    password: str,
    device: DeviceProfile,
    request_2fa_callback: Callable[[], Awaitable[str]],
) -> Optional[str]:
    """
    Main entry point.

    Logs into *email* / *password* using the supplied *device* profile,
    navigates to Google One, and returns the Gemini Pro offer link (or None).

    Raises :class:`GoogleAutomationError` if the driver cannot be started or the
    login step fails with an error.
    """
    driver: Optional[uc.Chrome] = None
    try:
        logger.info("Starting WebDriver for session %s", device.session_id)
        driver = _build_driver(device)

        logged_in = await _gmail_login(driver, email, password, request_2fa_callback)
        if not logged_in:
            raise GoogleAutomationError(
                "Login failed – please check your credentials."
            )

        offer_link = _navigate_google_one(driver)
        return offer_link

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
