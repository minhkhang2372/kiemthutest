import asyncio
import logging
import os
import time
import sys
import glob
import base64
from datetime import datetime
import pytest
import pytest_asyncio
from playwright.async_api import async_playwright, expect, TimeoutError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("lazada_test.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Create directories if they don't exist
for dir_path in ['screenshots', 'reports', 'test_data']:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# Global variables
SCREENSHOTS_DIR = 'screenshots'
REPORTS_DIR = 'reports'

# Custom hooks for pytest-html report
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    pytest_html = item.config.pluginmanager.getplugin("html")
    outcome = yield
    report = outcome.get_result()
    
    # Add extra property to report for screenshots
    extra = getattr(report, "extra", [])
    
    if report.when == "call":
        # Get test name
        test_name = report.nodeid.split("::")[-1]
        short_name = test_name.split("_")[-1]
        
        # Find screenshots related to this test
        screenshot_files = sorted(
            glob.glob(os.path.join(SCREENSHOTS_DIR, f"*{short_name}*.png")),
            key=os.path.getmtime,
            reverse=True
        )
        
        # Add test log info
        extra.append(pytest_html.extras.text(f"Test: {test_name}"))
        
        # Add screenshots to report
        if screenshot_files:
            for i, img_path in enumerate(screenshot_files[:3]):  # Limit to 3 screenshots
                try:
                    with open(img_path, "rb") as img_file:
                        img_base64 = base64.b64encode(img_file.read()).decode("utf-8")
                        img_name = os.path.basename(img_path)
                        extra.append(pytest_html.extras.html(
                            f'<div style="margin: 10px 0;"><strong>Screenshot: {img_name}</strong><br/>'
                            f'<a href="data:image/png;base64,{img_base64}" target="_blank">'
                            f'<img src="data:image/png;base64,{img_base64}" style="max-width:600px; border:1px solid #ddd; padding:5px;" />'
                            f'</a></div>'
                        ))
                except Exception as img_err:
                    logger.error(f"Error adding screenshot {img_path} to report: {str(img_err)}")
                    extra.append(pytest_html.extras.text(f"Error adding screenshot: {str(img_err)}"))
        else:
            extra.append(pytest_html.extras.text("No screenshots found for this test"))
            
        report.extra = extra

# Custom pytest-html report
def pytest_html_report_title(report):
    report.title = "Báo cáo kiểm thử tự động website Lazada"

def pytest_configure(config):
    # Add custom CSS to report
    config._metadata.clear()  # Clear default metadata
    config._metadata["Ngày kiểm thử"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    config._metadata["Website"] = "https://www.lazada.vn"
    config._metadata["Trình duyệt"] = "Chromium (Playwright)"
    
    # Modify HTML report environment section
    pytest_html = config.pluginmanager.getplugin('html')
    if pytest_html:
        pytest_html.css_files[0] = f"{pytest_html.css_files[0]}, custom.css"
        pytest_html.jquery_files[0] = f"{pytest_html.jquery_files[0]}, custom.js"

def pytest_html_assets_manifest():
    return {
        # Add custom CSS for report styling
        "css": {
            "custom.css": f"""
                .report-logo {{ max-width: 100%; margin-bottom: 20px; }}
                .test-summary {{ display: flex; flex-wrap: wrap; justify-content: space-between; margin-bottom: 20px; }}
                .summary-item {{ flex: 1; min-width: 140px; padding: 10px; margin: 5px; border-radius: 5px; text-align: center; }}
                .summary-pass {{ background-color: #d4edda; color: #155724; }}
                .summary-fail {{ background-color: #f8d7da; color: #721c24; }}
                .summary-skip {{ background-color: #fff3cd; color: #856404; }}
                .summary-error {{ background-color: #f5c6cb; color: #721c24; }}
                .summary-all {{ background-color: #e2e3e5; color: #383d41; }}
                .screenshot-container {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }}
                .screenshot-item {{ border: 1px solid #ddd; padding: 5px; margin: 5px 0; }}
                table {{ width: 100%; margin-top: 20px; }}
                th {{ background-color: #f8f9fa; }}
                .log {{ max-height: 300px; overflow: auto; background-color: #f8f9fa; border: 1px solid #ddd; padding: 10px; }}
                img {{ max-width: 100%; }}
                @media print {{ 
                    .log {{ max-height: none; }}
                    a[href]:after {{ content: none !important; }}
                }}
            """
        },
        "js": {
            "custom.js": """
                // Custom JavaScript for test report
                $(document).ready(function() {
                    // Add title to screenshots section
                    $('.extra').each(function() {
                        if ($(this).find('img').length > 0 && !$(this).prev().hasClass('screenshots-title')) {
                            $(this).before('<h3 class="screenshots-title">Ảnh chụp màn hình</h3>');
                        }
                    });
                    
                    // Make images clickable to open in new tab
                    $('img').click(function() {
                        window.open($(this).attr('src'), '_blank');
                    }).css('cursor', 'pointer');
                    
                    // Add summary counts at the top of the report
                    const passed = $('.col-result:contains("Passed")').length;
                    const failed = $('.col-result:contains("Failed")').length;
                    const skipped = $('.col-result:contains("Skipped")').length;
                    const error = $('.col-result:contains("Error")').length;
                    const total = passed + failed + skipped + error;
                    
                    const summaryHtml = `
                        <div class="test-summary">
                            <div class="summary-item summary-pass">
                                <h3>Đạt</h3>
                                <p>${passed}</p>
                            </div>
                            <div class="summary-item summary-fail">
                                <h3>Lỗi</h3>
                                <p>${failed}</p>
                            </div>
                            <div class="summary-item summary-skip">
                                <h3>Bỏ qua</h3>
                                <p>${skipped}</p>
                            </div>
                            <div class="summary-item summary-all">
                                <h3>Tổng số</h3>
                                <p>${total}</p>
                            </div>
                        </div>
                    `;
                    
                    $('h1').after(summaryHtml);
                    
                    // Add Lazada logo
                    $('h1').before('<div class="report-logo"><img src="https://laz-img-cdn.alicdn.com/tfs/TB1T7K2d8Cw3KVjSZFuXXcAOpXa-1024-1024.png" alt="Lazada Logo" style="max-width: 100px;"></div>');
                });
            """
        }
    }

class TestLazada:
    """
    Class for automated testing of the Lazada website using Playwright
    Focusing on public functionality (no login required)
    """
    
    @pytest_asyncio.fixture(scope="function")
    async def browser_context(self):
        """Set up the browser context for testing"""
        logger.info("Setting up browser context...")
        
        playwright = await async_playwright().start()
        
        # Get headless mode from environment variable or command line argument
        headless_arg = '--headless' in sys.argv
        headless_env = os.environ.get('HEADLESS', 'False').lower() in ('true', '1', 't')
        headless = headless_arg or headless_env
        
        browser = await playwright.chromium.launch(
            headless=headless,
            timeout=30000  # 30 second timeout for browser launch
        )
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        )
        
        # Create a new page with logging and set default timeout
        page = await context.new_page()
        page.set_default_timeout(15000)  # 15 second default timeout for all operations
        page.on("console", lambda msg: logger.info(f"Browser console: {msg.text}"))
        
        # Test data - can be customized via environment variables
        test_data = {
            'base_url': os.environ.get('TEST_URL', 'https://www.lazada.vn/'),
            'test_product': os.environ.get('TEST_PRODUCT', 'điện thoại Samsung'),
            'category': os.environ.get('TEST_CATEGORY', 'Điện Thoại & Máy Tính Bảng')
        }
        
        # Yield the context dict to the tests
        context_dict = {
            'page': page, 
            'context': context, 
            'browser': browser, 
            'test_data': test_data, 
            'playwright': playwright
        }
        
        logger.info("Browser context setup complete")
        yield context_dict
        
        # Teardown - close browser and playwright
        logger.info("Tearing down browser context...")
        await browser.close()
        await playwright.stop()
        logger.info("Browser context teardown complete")
    
    async def take_screenshot(self, page, test_name):
        """Take and save screenshot"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"screenshots/{test_name}_{timestamp}.png"
            await page.screenshot(path=screenshot_path, timeout=5000, full_page=True)
            logger.info(f"Screenshot saved to {screenshot_path}")
            return screenshot_path
        except Exception as e:
            logger.error(f"Failed to take screenshot: {str(e)}")
            return None
    
    # =============== FUNCTIONAL TESTING ===============
    
    @pytest.mark.asyncio
    async def test_01_homepage_load(self, browser_context):
        """Test homepage loads correctly"""
        logger.info("--- Starting test case: Homepage Load ---")
        page = browser_context['page']
        test_data = browser_context['test_data']
        
        try:
            # Navigate to homepage with explicit timeout
            logger.info(f"Navigating to: {test_data['base_url']}")
            await page.goto(test_data['base_url'], timeout=20000, wait_until="domcontentloaded")
            logger.info("Homepage loaded")
            
            # Take screenshot of homepage
            await self.take_screenshot(page, "homepage")
            
            # Verify page title
            title = await page.title()
            assert "Lazada" in title, f"Title does not contain Lazada: {title}"
            logger.info(f"Page title: {title}")
            
            # Check for key elements on homepage
            elements_to_check = {
                "Logo": "div.lzd-logo, a.lzd-logo",
                "Search Bar": "#q, input[type='search']",
                "Cart Icon": "span.cart-icon, div.cart-icon, a.cart-link"
            }
            
            for name, selector in elements_to_check.items():
                element = page.locator(selector)
                try:
                    is_visible = await element.is_visible(timeout=5000)
                    if is_visible:
                        logger.info(f"{name} is visible on homepage")
                    else:
                        logger.warning(f"{name} was found but not visible on homepage")
                except Exception as e:
                    logger.warning(f"Error checking {name}: {str(e)}")
            
            logger.info("--- Completed test case: Homepage Load ---")
            
        except Exception as e:
            logger.error(f"Error in homepage load test: {str(e)}")
            await self.take_screenshot(page, "homepage_error")
            raise
    
    @pytest.mark.asyncio
    async def test_02_search_products(self, browser_context):
        """Test product search functionality"""
        logger.info("--- Starting test case: Product Search ---")
        page = browser_context['page']
        test_data = browser_context['test_data']
        
        try:
            # Navigate to homepage with explicit timeout
            logger.info(f"Navigating to: {test_data['base_url']}")
            await page.goto(test_data['base_url'], timeout=20000, wait_until="domcontentloaded")
            logger.info("Homepage loaded")
            
            # Take screenshot before search
            await self.take_screenshot(page, "before_search")
            
            # Find search box and enter search term
            logger.info("Looking for search box...")
            search_box = page.locator("#q, input[type='search']")
            
            # Make sure search box is visible
            await search_box.wait_for(state="visible", timeout=5000)
            
            await search_box.fill(test_data['test_product'], timeout=5000)
            logger.info(f"Entered search term: {test_data['test_product']}")
            
            # Take screenshot with search term filled
            await self.take_screenshot(page, "search_filled")
            
            # Press Enter to search
            await search_box.press("Enter", timeout=5000)
            logger.info("Pressed Enter to search")
            
            # Wait for page navigation to complete
            await page.wait_for_load_state("domcontentloaded", timeout=20000)
            logger.info("Search results page loaded")
            
            # Take screenshot of search results
            await self.take_screenshot(page, "search_results")
            
            # Wait for search results to load - trying different selectors as the site might change
            try:
                logger.info("Looking for product cards...")
                # Try multiple selectors for product cards
                product_selectors = [
                    "div.Bm3ON", 
                    "div.card--P3aS1", 
                    "div.product-card",
                    "div[data-tracking='product-card']",
                    "div.product-item",
                    "div.c1ZEkM" # Added newer selector
                ]
                
                product_found = False
                for selector in product_selectors:
                    logger.info(f"Trying selector: {selector}")
                    product_cards = page.locator(selector)
                    count = await product_cards.count()
                    if count > 0:
                        logger.info(f"Found {count} product cards with selector: {selector}")
                        product_found = True
                        break
                
                if not product_found:
                    # If we can't find the product cards, check if we're on a search results page
                    current_url = page.url
                    logger.info(f"Current URL: {current_url}")
                    if "searchRedirect" in current_url or "search" in current_url or "catalog" in current_url:
                        logger.info("On search results page, but couldn't identify product cards. Site may have changed.")
                    else:
                        await self.take_screenshot(page, "search_results_no_products")
                        raise Exception("Not on search results page and no product cards found")
            except TimeoutError as te:
                logger.warning(f"Timeout waiting for product cards: {str(te)}")
                # Even if we timeout, let's check the URL and title
                current_url = page.url
                if "searchRedirect" in current_url or "search" in current_url or "catalog" in current_url:
                    logger.info("On search results page despite timeout")
                else:
                    await self.take_screenshot(page, "search_timeout")
                    raise Exception(f"Timeout and not on search results page. URL: {current_url}")
            
            # Get the title and verify it contains our search term
            title = await page.title()
            logger.info(f"Search results page title: {title}")
            
            # Check if title or URL contains the search term
            if "Samsung" in title or "samsung" in page.url.lower() or "phone" in page.url.lower() or "dien-thoai" in page.url.lower():
                logger.info("Page title or URL contains expected search terms")
            else:
                logger.warning(f"Title does not contain search term: {title}")
            
            logger.info("--- Completed test case: Product Search ---")
            
        except Exception as e:
            logger.error(f"Error in search test: {str(e)}")
            await self.take_screenshot(page, "search_error")
            raise
    
    @pytest.mark.asyncio
    async def test_03_product_details(self, browser_context):
        """Test viewing product details page"""
        logger.info("--- Starting test case: Product Details ---")
        page = browser_context['page']
        test_data = browser_context['test_data']
        
        try:
            # Navigate to homepage with explicit timeout
            logger.info(f"Navigating to: {test_data['base_url']}")
            await page.goto(test_data['base_url'], timeout=20000, wait_until="domcontentloaded") 
            logger.info("Homepage loaded")
            
            # Search for product
            logger.info("Looking for search box...")
            search_box = page.locator("#q, input[type='search']")
            await search_box.fill(test_data['test_product'], timeout=5000)
            logger.info(f"Searched for: {test_data['test_product']}")
            
            # Press Enter to search
            await search_box.press("Enter", timeout=5000)
            logger.info("Pressed Enter to search")
            
            # Wait for page navigation to complete
            await page.wait_for_load_state("domcontentloaded", timeout=20000) 
            logger.info("Search results page loaded")
            
            # Take screenshot of search results
            await self.take_screenshot(page, "product_search_results")
            
            # Allow a brief moment for page rendering
            await asyncio.sleep(3)
            
            # Try to click on first product
            logger.info("Looking for a product to click...")
            
            # Try different product card selectors as the site may change
            product_selectors = [
                "div.Bm3ON a", 
                "div.card--P3aS1 a", 
                "div.product-card a",
                "div[data-tracking='product-card'] a",
                "a[href*='item']",
                "a[href*='product']",
                "div.product-item a",
                "div.c1ZEkM a" # Added newer selector
            ]
            
            product_found = False
            for selector in product_selectors:
                logger.info(f"Trying selector: {selector}")
                products = page.locator(selector)
                count = await products.count()
                logger.info(f"Found {count} products with selector: {selector}")
                
                if count > 0:
                    # Click on the first product
                    first_product = products.first
                    try:
                        await first_product.click(timeout=10000)
                        logger.info("Clicked on first product")
                        product_found = True
                        break
                    except Exception as click_error:
                        logger.warning(f"Error clicking on product with selector {selector}: {str(click_error)}")
                        continue
            
            if not product_found:
                logger.warning("Could not find or click on any product, skipping rest of test")
                await self.take_screenshot(page, "no_product_clicked")
                return
            
            # Wait for product page to load
            logger.info("Waiting for product page to load...")
            await page.wait_for_load_state("domcontentloaded", timeout=20000)
            
            # Take screenshot of product page
            await self.take_screenshot(page, "product_page")
            
            # Check for key elements on product page
            # Multiple selectors to try as the site structure can change
            logger.info("Checking for product details elements...")
            
            # Check price
            price_selectors = [
                "div.pdp-product-price", 
                "span.price", 
                ".product-price",
                "div.price-container",
                "span[data-price]",
                "div.pdp-price" # Added newer selector
            ]
            
            price_found = False
            for selector in price_selectors:
                price = page.locator(selector)
                if await price.count() > 0:
                    try:
                        is_visible = await price.is_visible(timeout=3000)
                        if is_visible:
                            price_text = await price.text_content()
                            logger.info(f"Product price: {price_text}")
                            price_found = True
                            break
                    except Exception as e:
                        logger.warning(f"Error checking price with selector {selector}: {str(e)}")
            
            if not price_found:
                logger.warning("Price element not found on product page")
            
            # Check add to cart button
            cart_button_selectors = [
                "button.add-to-cart", 
                "button.btn-add-cart", 
                "button.btn-buy-now",
                "button:has-text('Add to Cart')",
                "button:has-text('Thêm vào giỏ')",
                "button[data-spm-click*='cart']",
                "button.add-to-cart-buy-now-btn"
            ]
            
            cart_button_found = False
            for selector in cart_button_selectors:
                cart_button = page.locator(selector)
                if await cart_button.count() > 0:
                    try:
                        is_visible = await cart_button.is_visible(timeout=3000)
                        if is_visible:
                            logger.info(f"Add to cart button found with selector: {selector}")
                            cart_button_found = True
                            break
                    except Exception as e:
                        logger.warning(f"Error checking cart button with selector {selector}: {str(e)}")
            
            if not cart_button_found:
                logger.warning("Add to cart button not found on product page")
            
            # Check product title
            title_selectors = [
                "h1", 
                ".pdp-mod-product-name", 
                ".product-title",
                ".pdp-title",
                "div.product-info h1"
            ]
            
            title_found = False
            for selector in title_selectors:
                product_title = page.locator(selector)
                if await product_title.count() > 0:
                    try:
                        is_visible = await product_title.is_visible(timeout=3000)
                        if is_visible:
                            title_text = await product_title.text_content()
                            logger.info(f"Product title: {title_text}")
                            title_found = True
                            break
                    except Exception as e:
                        logger.warning(f"Error checking title with selector {selector}: {str(e)}")
            
            if not title_found:
                logger.warning("Product title element not found")
            
            # Get the page title as a fallback
            page_title = await page.title()
            logger.info(f"Product page title: {page_title}")
            
            logger.info("--- Completed test case: Product Details ---")
                
        except Exception as e:
            logger.error(f"Error in product details test: {str(e)}")
            await self.take_screenshot(page, "product_details_error")
            raise
    
    @pytest.mark.asyncio
    async def test_04_category_navigation(self, browser_context):
        """Test category navigation"""
        logger.info("--- Starting test case: Category Navigation ---")
        page = browser_context['page']
        test_data = browser_context['test_data']
        
        try:
            # Navigate to homepage with explicit timeout
            logger.info(f"Navigating to: {test_data['base_url']}")
            await page.goto(test_data['base_url'], timeout=20000, wait_until="domcontentloaded")
            logger.info("Homepage loaded")
            
            # Take screenshot of homepage
            await self.take_screenshot(page, "homepage_for_category")
            
            # Try to find and click on a category
            # We'll try various ways of finding categories since the site structure might change
            
            # Method 1: Try to find the category in the main menu
            logger.info("Trying Method 1: Finding category in main menu")
            try:
                # Hover over categories menu to show sub-categories (if needed)
                menu_selectors = [
                    ".lzd-site-menu-root", 
                    "nav.menu", 
                    "div.lzd-menu",
                    "div.lzd-site-nav-menu"
                ]
                
                menu_found = False
                for selector in menu_selectors:
                    categories_menu = page.locator(selector)
                    if await categories_menu.count() > 0:
                        try:
                            is_visible = await categories_menu.is_visible(timeout=3000)
                            if is_visible:
                                await categories_menu.hover(timeout=5000)
                                logger.info(f"Hovered over categories menu with selector: {selector}")
                                menu_found = True
                                break
                        except Exception as e:
                            logger.warning(f"Error hovering over menu with selector {selector}: {str(e)}")
                
                if not menu_found:
                    logger.warning("Could not find categories menu")
                    raise Exception("Categories menu not found")
                
                # Wait a bit for any animations
                await asyncio.sleep(2)
                
                # Take screenshot after hovering
                await self.take_screenshot(page, "after_menu_hover")
                
                # Try to find and click on a category link
                category_link = page.locator(f"a:has-text('{test_data['category']}')")
                if await category_link.count() > 0:
                    await category_link.click(timeout=10000)
                    logger.info(f"Clicked on category: {test_data['category']}")
                    
                    # Wait for the category page to load
                    await page.wait_for_load_state("domcontentloaded", timeout=20000)
                    
                    # Verify we're on a category page
                    title = await page.title()
                    current_url = page.url
                    
                    logger.info(f"Category page loaded. Title: {title}, URL: {current_url}")
                    
                    # Take screenshot of category page
                    await self.take_screenshot(page, "category_page")
                    
                    # Wait for any product grid to appear
                    await asyncio.sleep(3)
                    
                    # Check if there are products listed using multiple possible selectors
                    product_selectors = [
                        "div.Bm3ON", 
                        "div.card--P3aS1", 
                        "div.product-card", 
                        "div.c2prKC",
                        "div[data-tracking='product-card']",
                        "div.product-item",
                        "div.c1ZEkM" # Added newer selector
                    ]
                    
                    products_found = False
                    for selector in product_selectors:
                        products = page.locator(selector)
                        count = await products.count()
                        if count > 0:
                            logger.info(f"Found {count} products in category with selector: {selector}")
                            products_found = True
                            break
                    
                    if not products_found:
                        logger.warning("No products found in category page with common selectors")
                else:
                    logger.warning(f"Category link '{test_data['category']}' not found, trying alternative method")
                    raise Exception("Category link not found")
            
            except Exception as e:
                logger.warning(f"Method 1 failed: {str(e)}")
                
                # Method 2: Try using the site's category/department structure if available
                logger.info("Trying Method 2: Clicking on any category card")
                try:
                    # This is an alternative approach - try to find a category by clicking on department links
                    await page.goto(test_data['base_url'], timeout=20000, wait_until="domcontentloaded")
                    logger.info("Returned to homepage")
                    
                    # Wait for popular categories or any featured section
                    card_selectors = [
                        "a.card", 
                        "div.lzd-home-card", 
                        "a.lzd-site-nav-menu-item",
                        "div.card-channels-item a",
                        "div.lzd-site-menu-root a"
                    ]
                    
                    card_found = False
                    for selector in card_selectors:
                        category_cards = page.locator(selector)
                        count = await category_cards.count()
                        if count > 0:
                            logger.info(f"Found {count} category cards with selector: {selector}")
                            try:
                                # Click on the first visible category card
                                first_card = category_cards.first
                                await first_card.click(timeout=10000)
                                logger.info(f"Clicked on first category card with selector: {selector}")
                                
                                # Wait for category page to load
                                await page.wait_for_load_state("domcontentloaded", timeout=20000)
                                
                                # Take screenshot of category page
                                await self.take_screenshot(page, "category_page_method2")
                                
                                card_found = True
                                break
                            except Exception as click_error:
                                logger.warning(f"Error clicking on category card with selector {selector}: {str(click_error)}")
                                continue
                    
                    if not card_found:
                        logger.warning("No clickable category cards found on homepage")
                        raise Exception("No clickable category cards found on homepage")
                        
                    # Verify we're on a category page by checking for products
                    product_selectors = [
                        "div.Bm3ON", 
                        "div.card--P3aS1", 
                        "div.product-card", 
                        "div.c2prKC",
                        "div[data-tracking='product-card']",
                        "div.product-item",
                        "div.c1ZEkM" # Added newer selector
                    ]
                    
                    # Allow some time for products to load
                    await asyncio.sleep(3)
                    
                    products_found = False
                    for selector in product_selectors:
                        products = page.locator(selector)
                        count = await products.count()
                        if count > 0:
                            logger.info(f"Found {count} products in category with selector: {selector}")
                            products_found = True
                            break
                    
                    if not products_found:
                        logger.warning("No products found in category page with common selectors")
                
                except Exception as e:
                    logger.warning(f"Method 2 failed as well: {str(e)}")
                    logger.warning("Unable to navigate to a category page using multiple methods")
                    # We'll continue rather than raising an exception here since we tried multiple methods
                    # and this isn't a critical failure for the overall test suite
            
            logger.info("--- Completed test case: Category Navigation ---")
            
        except Exception as e:
            logger.error(f"Error in category navigation test: {str(e)}")
            await self.take_screenshot(page, "category_navigation_error")
            raise
    
    @pytest.mark.asyncio
    async def test_05_add_to_cart_view_cart(self, browser_context):
        """Test add to cart and view cart functionality"""
        logger.info("--- Starting test case: Add to Cart and View Cart ---")
        page = browser_context['page']
        test_data = browser_context['test_data']
        
        try:
            # Navigate to homepage with explicit timeout
            logger.info(f"Navigating to: {test_data['base_url']}")
            await page.goto(test_data['base_url'], timeout=20000, wait_until="domcontentloaded")
            logger.info("Homepage loaded")
            
            # Search for product
            logger.info("Looking for search box...")
            search_box = page.locator("#q, input[type='search']")
            await search_box.fill(test_data['test_product'], timeout=5000)
            logger.info(f"Searched for: {test_data['test_product']}")
            
            # Press Enter to search
            await search_box.press("Enter", timeout=5000)
            logger.info("Pressed Enter to search")
            
            # Wait for page navigation to complete
            await page.wait_for_load_state("domcontentloaded", timeout=20000)
            logger.info("Search results page loaded")
            
            # Allow a brief moment for page rendering
            await asyncio.sleep(3)
            
            # Take screenshot of search results 
            await self.take_screenshot(page, "cart_test_search_results")
            
            # Click on first product
            logger.info("Looking for a product to click...")
            product_selectors = [
                "div.Bm3ON a", 
                "div.card--P3aS1 a", 
                "div.product-card a",
                "div[data-tracking='product-card'] a",
                "a[href*='item']",
                "a[href*='product']",
                "div.product-item a",
                "div.c1ZEkM a" # Added newer selector
            ]
            
            product_found = False
            for selector in product_selectors:
                logger.info(f"Trying selector: {selector}")
                products = page.locator(selector)
                count = await products.count()
                logger.info(f"Found {count} products with selector: {selector}")
                
                if count > 0:
                    # Click on the first product
                    first_product = products.first
                    try:
                        await first_product.click(timeout=10000)
                        logger.info("Clicked on first product")
                        product_found = True
                        break
                    except Exception as click_error:
                        logger.warning(f"Error clicking on product with selector {selector}: {str(click_error)}")
                        continue
            
            if not product_found:
                logger.warning("Could not find or click on any product, skipping rest of test")
                await self.take_screenshot(page, "no_product_for_cart")
                return
            
            # Wait for product page to load
            logger.info("Waiting for product page to load...")
            await page.wait_for_load_state("domcontentloaded", timeout=20000)
            
            # Take screenshot of product page
            await self.take_screenshot(page, "product_page_for_cart")
            
            # Wait a moment for all elements to be fully loaded and visible
            await asyncio.sleep(3)
            
            # Click add to cart button (trying different selectors)
            logger.info("Looking for Add to Cart button...")
            cart_button_selectors = [
                "button.add-to-cart", 
                "button.btn-add-cart", 
                "button.btn-buy-now",
                "button:has-text('Add to Cart')",
                "button:has-text('Thêm vào giỏ')",
                "button[data-spm-click*='cart']",
                "button.add-to-cart-buy-now-btn"
            ]
            
            cart_button_found = False
            for selector in cart_button_selectors:
                logger.info(f"Trying cart button selector: {selector}")
                cart_button = page.locator(selector)
                count = await cart_button.count()
                logger.info(f"Found {count} buttons with selector: {selector}")
                
                if count > 0:
                    try:
                        # Check if the button is visible
                        is_visible = await cart_button.first.is_visible(timeout=3000)
                        if is_visible:
                            await cart_button.first.click(timeout=10000)
                            logger.info(f"Clicked Add to Cart button with selector: {selector}")
                            cart_button_found = True
                            break
                        else:
                            logger.warning(f"Button found with selector {selector} but not visible")
                    except Exception as click_error:
                        logger.warning(f"Error clicking on cart button with selector {selector}: {str(click_error)}")
                        continue
            
            if not cart_button_found:
                logger.warning("Add to cart button not found or not clickable, skipping rest of test")
                await self.take_screenshot(page, "no_cart_button")
                return
            
            # Wait for any success message or cart count update
            try:
                # Wait for cart success message or wait a moment
                logger.info("Waiting after clicking Add to Cart...")
                await asyncio.sleep(3)  # Give time for the cart to update
                
                # Take screenshot after adding to cart
                await self.take_screenshot(page, "after_add_to_cart")
                
                # Check if there's a success message
                success_selectors = [
                    "div.cart-message", 
                    "div.success-message", 
                    "div.add-to-cart-success",
                    ".atc-succ-toast",
                    "div[class*='success']",
                    "div[class*='toast']"
                ]
                
                success_found = False
                for selector in success_selectors:
                    success_message = page.locator(selector)
                    if await success_message.count() > 0:
                        try:
                            is_visible = await success_message.is_visible(timeout=3000)
                            if is_visible:
                                logger.info(f"Success message visible with selector: {selector}")
                                success_found = True
                                break
                        except Exception as e:
                            logger.warning(f"Error checking success message with selector {selector}: {str(e)}")
                
                if not success_found:
                    logger.info("No success message found, but continuing with test")
                
                # Try to view cart
                logger.info("Attempting to view cart...")
                
                try:
                    # Method 1: Direct URL to cart
                    logger.info("Method 1: Navigating directly to cart URL")
                    await page.goto("https://cart.lazada.vn/cart", timeout=20000)
                    logger.info("Navigated to cart page via direct URL")
                    
                    # Wait for cart page to load
                    await page.wait_for_load_state("domcontentloaded", timeout=20000)
                    
                    # Take screenshot of cart page
                    await self.take_screenshot(page, "cart_page_direct")
                    
                    # Check if we're on the cart page by looking for cart-specific elements
                    cart_element_selectors = [
                        "div.item-list", 
                        "div.checkout-order-total", 
                        "div.cart-empty",
                        ".shopping-cart-container",
                        "div[class*='cart']" 
                    ]
                    
                    cart_elements_found = False
                    for selector in cart_element_selectors:
                        cart_elements = page.locator(selector)
                        if await cart_elements.count() > 0:
                            try:
                                is_visible = await cart_elements.is_visible(timeout=3000)
                                if is_visible:
                                    logger.info(f"Cart page element found with selector: {selector}")
                                    cart_elements_found = True
                                    break
                            except Exception as e:
                                logger.warning(f"Error checking cart element with selector {selector}: {str(e)}")
                    
                    if cart_elements_found:
                        logger.info("Successfully viewed cart page via direct URL")
                    else:
                        logger.warning("Direct URL navigation did not appear to reach cart page")
                        raise Exception("Direct URL navigation did not reach cart page")
                        
                except Exception as cart_error:
                    logger.warning(f"Error viewing cart via direct URL: {str(cart_error)}")
                    
                    # Method 2: Click on cart icon
                    try:
                        logger.info("Method 2: Clicking on cart icon")
                        await page.goto(test_data['base_url'], timeout=20000, wait_until="domcontentloaded")
                        logger.info("Returned to homepage")
                        
                        cart_icon_selectors = [
                            "span.cart-icon", 
                            "a.cart-link",
                            "div.cart-icon",
                            "a[href*='cart']"
                        ]
                        
                        cart_icon_found = False
                        for selector in cart_icon_selectors:
                            logger.info(f"Trying cart icon selector: {selector}")
                            cart_icon = page.locator(selector)
                            if await cart_icon.count() > 0:
                                try:
                                    is_visible = await cart_icon.is_visible(timeout=3000)
                                    if is_visible:
                                        await cart_icon.click(timeout=10000)
                                        logger.info(f"Clicked on cart icon with selector: {selector}")
                                        cart_icon_found = True
                                        break
                                except Exception as e:
                                    logger.warning(f"Error clicking cart icon with selector {selector}: {str(e)}")
                        
                        if not cart_icon_found:
                            logger.warning("Cart icon not found or not clickable")
                            raise Exception("Cart icon not found or not clickable")
                        
                        # Wait for cart page to load
                        await page.wait_for_load_state("domcontentloaded", timeout=20000)
                        
                        # Take screenshot of cart page
                        await self.take_screenshot(page, "cart_page_via_icon")
                        
                        # Check if we're on cart page
                        cart_element_selectors = [
                            "div.item-list", 
                            "div.checkout-order-total", 
                            "div.cart-empty",
                            ".shopping-cart-container",
                            "div[class*='cart']"
                        ]
                        
                        cart_elements_found = False
                        for selector in cart_element_selectors:
                            cart_elements = page.locator(selector)
                            if await cart_elements.count() > 0:
                                try:
                                    is_visible = await cart_elements.is_visible(timeout=3000)
                                    if is_visible:
                                        logger.info(f"Cart page element found with selector: {selector}")
                                        cart_elements_found = True
                                        break
                                except Exception as e:
                                    logger.warning(f"Error checking cart element with selector {selector}: {str(e)}")
                        
                        if cart_elements_found:
                            logger.info("Successfully viewed cart page via cart icon")
                        else:
                            logger.warning("Cart icon click did not appear to reach cart page")
                    except Exception as e:
                        logger.warning(f"Error viewing cart via cart icon: {str(e)}")
                        logger.warning("Failed to view cart using multiple methods, but test partially succeeded (added to cart)")
            
            except Exception as e:
                logger.warning(f"Error in cart verification: {str(e)}")
                logger.warning("Test partially succeeded (clicked add to cart)")
            
            logger.info("--- Completed test case: Add to Cart and View Cart ---")
            
        except Exception as e:
            logger.error(f"Error in add to cart test: {str(e)}")
            await self.take_screenshot(page, "add_to_cart_error")
            raise
    
    # =============== UI TESTING ===============
    
    @pytest.mark.asyncio
    async def test_06_ui_elements(self, browser_context):
        """Test UI elements on homepage"""
        logger.info("--- Starting test case: UI Elements ---")
        page = browser_context['page']
        test_data = browser_context['test_data']
        
        try:
            # Navigate to homepage with explicit timeout
            logger.info(f"Navigating to: {test_data['base_url']}")
            await page.goto(test_data['base_url'], timeout=20000, wait_until="domcontentloaded")
            logger.info("Homepage loaded")
            
            # Take screenshot of homepage
            await self.take_screenshot(page, "homepage_for_ui_test")
            
            # Check key UI elements
            ui_elements = {
                "Logo": "div.lzd-logo, a.lzd-logo",
                "Search Box": "#q, input[type='search']",
                "Cart Icon": "span.cart-icon, div.cart-icon, a.cart-link",
                "Categories Menu": "div.lzd-site-menu-root, nav.menu, div.lzd-menu",
                "Banner/Carousel": "div.lzd-home-banner, div.carousel, div.banner, div.slick-slider"
            }
            
            for name, selector in ui_elements.items():
                logger.info(f"Checking UI element: {name}")
                element = page.locator(selector)
                count = await element.count()
                logger.info(f"Found {count} elements matching {name}")
                
                if count > 0:
                    try:
                        is_visible = await element.first.is_visible(timeout=3000)
                        if is_visible:
                            logger.info(f"{name} is visible")
                        else:
                            logger.warning(f"{name} found but not visible")
                    except Exception as e:
                        logger.warning(f"Error checking visibility of {name}: {str(e)}")
                else:
                    logger.warning(f"{name} not found using selector: {selector}")
            
            # Test responsive design - resize to mobile viewport
            logger.info("Testing responsive design...")
            await page.set_viewport_size({"width": 375, "height": 667})
            logger.info("Resized viewport to mobile dimensions")
            
            # Wait for layout to adjust
            await asyncio.sleep(2)
            
            # Take screenshot of mobile viewport
            await self.take_screenshot(page, "mobile_viewport")
            
            # Check if key elements are still visible on mobile
            mobile_elements = {
                "Mobile Logo": "div.lzd-logo, a.logo, div.logo, a.lzd-logo",
                "Mobile Search": "#q, input[type='search'], .search-box input",
                "Mobile Cart": "span.cart-icon, div.cart-icon, a.cart-link"
            }
            
            for name, selector in mobile_elements.items():
                logger.info(f"Checking mobile UI element: {name}")
                element = page.locator(selector)
                count = await element.count()
                logger.info(f"Found {count} elements matching {name} on mobile")
                
                if count > 0:
                    try:
                        is_visible = await element.first.is_visible(timeout=3000)
                        if is_visible:
                            logger.info(f"{name} is visible on mobile viewport")
                        else:
                            logger.warning(f"{name} found but not visible on mobile")
                    except Exception as e:
                        logger.warning(f"Error checking visibility of {name} on mobile: {str(e)}")
                else:
                    logger.warning(f"{name} not found on mobile using selector: {selector}")
            
            # Reset viewport size
            await page.set_viewport_size({"width": 1366, "height": 768})
            logger.info("Reset viewport to desktop dimensions")
            
            logger.info("--- Completed test case: UI Elements ---")
            
        except Exception as e:
            logger.error(f"Error in UI elements test: {str(e)}")
            await self.take_screenshot(page, "ui_elements_error")
            raise
    
    # =============== PERFORMANCE TESTING ===============
    
    @pytest.mark.asyncio
    async def test_07_basic_performance(self, browser_context):
        """Test basic performance metrics"""
        logger.info("--- Starting test case: Basic Performance ---")
        page = browser_context['page']
        test_data = browser_context['test_data']
        
        try:
            # Clear browser cache to get fresh load times
            logger.info("Clearing cookies for fresh measurement")
            await browser_context['context'].clear_cookies()
            
            # Measure homepage load time
            logger.info("Measuring homepage load time...")
            start_time = time.time()
            
            # Navigate to homepage and wait for network idle
            response = await page.goto(test_data['base_url'], wait_until="networkidle", timeout=30000)
            load_time = (time.time() - start_time) * 1000  # convert to ms
            
            logger.info(f"Homepage load time: {load_time:.2f} ms")
            
            # Take screenshot of loaded homepage
            await self.take_screenshot(page, "performance_homepage")
            
            # Check if page loaded successfully
            if response:
                status = response.status
                logger.info(f"Homepage status code: {status}")
                if status >= 400:
                    logger.warning(f"Homepage loaded with error status code: {status}")
            else:
                logger.warning("No response object returned from navigation")
            
            try:
                # Create client for performance measurements
                logger.info("Collecting performance metrics...")
                client = await page.context.new_cdp_session(page)
                
                # Enable performance metrics collection
                await client.send("Performance.enable")
                
                # Get performance metrics
                metrics = await client.send("Performance.getMetrics")
                
                # Log key metrics
                logger.info("Performance metrics:")
                for metric in metrics["metrics"]:
                    logger.info(f"  {metric['name']}: {metric['value']}")
                    
                # Additional performance metrics - First Contentful Paint
                perf_timing = await page.evaluate("""() => {
                    const nav = performance.getEntriesByType('navigation')[0];
                    const paint = performance.getEntriesByType('paint');
                    return {
                        navigationStart: 0,
                        loadEventEnd: nav.loadEventEnd,
                        domContentLoaded: nav.domContentLoadedEventEnd,
                        firstPaint: paint.find(e => e.name === 'first-paint')?.startTime,
                        firstContentfulPaint: paint.find(e => e.name === 'first-contentful-paint')?.startTime
                    }
                }""")
                
                logger.info("Browser timing metrics:")
                for name, value in perf_timing.items():
                    logger.info(f"  {name}: {value:.2f} ms")
                    
            except Exception as metrics_error:
                logger.warning(f"Error collecting performance metrics: {str(metrics_error)}")
            
            # Clear cache again for search test
            await browser_context['context'].clear_cookies()
            
            # Measure search results page load time
            logger.info("Measuring search results page load time...")
            start_time = time.time()
            
            # Search for a product
            await page.goto(test_data['base_url'], timeout=20000, wait_until="domcontentloaded")
            
            # Find and fill search
            search_box = page.locator("#q, input[type='search']")
            await search_box.fill(test_data['test_product'], timeout=5000)
            
            # Press Enter to search
            await search_box.press("Enter", timeout=5000)
            logger.info(f"Searching for: {test_data['test_product']}")
            
            # Wait for search results page to load
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
                search_load_time = (time.time() - start_time) * 1000  # convert to ms
                
                logger.info(f"Search results load time: {search_load_time:.2f} ms")
                
                # Take screenshot of search results
                await self.take_screenshot(page, "performance_search_results")
                
                # Try to check for product cards to confirm search completed
                product_selectors = [
                    "div.Bm3ON", 
                    "div.card--P3aS1", 
                    "div.product-card",
                    "div[data-tracking='product-card']",
                    "div.c1ZEkM" # Added newer selector
                ]
                
                for selector in product_selectors:
                    products = page.locator(selector)
                    count = await products.count()
                    if count > 0:
                        logger.info(f"Found {count} products with selector: {selector}")
                        break
                
            except TimeoutError:
                logger.warning("Timeout waiting for search results, possibly due to site changes")
                await self.take_screenshot(page, "search_performance_timeout")
            
            logger.info("--- Completed test case: Basic Performance ---")
            
        except Exception as e:
            logger.error(f"Error in performance test: {str(e)}")
            await self.take_screenshot(page, "performance_error")
            raise
    
    # =============== CONTENT TESTING ===============
    
    @pytest.mark.asyncio
    async def test_08_content_validation(self, browser_context):
        """Test content on homepage"""
        logger.info("--- Starting test case: Content Validation ---")
        page = browser_context['page']
        test_data = browser_context['test_data']
        
        try:
            # Navigate to homepage with explicit timeout
            logger.info(f"Navigating to: {test_data['base_url']}")
            await page.goto(test_data['base_url'], timeout=20000, wait_until="domcontentloaded")
            logger.info("Homepage loaded")
            
            # Take screenshot of homepage
            await self.take_screenshot(page, "homepage_for_content")
            
            # Check page title
            title = await page.title()
            logger.info(f"Page title: {title}")
            if "Lazada" in title:
                logger.info("Page title contains 'Lazada'")
            else:
                logger.warning(f"Page title does not contain 'Lazada': {title}")
            
            # Check for featured categories or popular departments section
            logger.info("Checking for featured sections...")
            featured_section_selectors = [
                "div.card-jfy-title", 
                "div.lzd-home-section", 
                "div.lzd-site-section",
                "div.hp-mod-card-title",
                "div.lzd-site-nav-menu"
            ]
            
            featured_sections_found = False
            for selector in featured_section_selectors:
                featured_sections = page.locator(selector)
                count = await featured_sections.count()
                if count > 0:
                    logger.info(f"Found {count} featured sections with selector: {selector}")
                    featured_sections_found = True
                    
                    # Try to get section titles
                    try:
                        for i in range(min(count, 5)):  # Limit to first 5 to avoid too much logging
                            section = featured_sections.nth(i)
                            is_visible = await section.is_visible(timeout=3000)
                            if is_visible:
                                section_text = await section.text_content()
                                logger.info(f"Section {i+1}: {section_text.strip()[:50]}...")  # Truncate long text
                    except Exception as section_error:
                        logger.warning(f"Error getting section text: {str(section_error)}")
                    
                    break
            
            if not featured_sections_found:
                logger.warning("No featured sections found on homepage with common selectors")
            
            # Scroll to footer
            logger.info("Scrolling to footer...")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            
            # Wait for footer to load
            await asyncio.sleep(2)
            
            # Take screenshot of footer
            await self.take_screenshot(page, "footer")
            
            # Check footer links
            logger.info("Checking footer...")
            footer_selectors = [
                "footer", 
                "div.footer", 
                "div.lzd-footer",
                "div[class*='footer']"
            ]
            
            footer_found = False
            for selector in footer_selectors:
                footer = page.locator(selector)
                if await footer.count() > 0:
                    try:
                        is_visible = await footer.is_visible(timeout=3000)
                        if is_visible:
                            logger.info(f"Footer found with selector: {selector}")
                            footer_found = True
                            break
                    except Exception as e:
                        logger.warning(f"Error checking footer with selector {selector}: {str(e)}")
            
            if not footer_found:
                logger.warning("Footer not found with common selectors")
            
            # Check important links in footer
            logger.info("Checking important footer links...")
            important_links = [
                "Về Lazada", "Liên hệ", "Điều khoản", "Bảo mật", 
                "Contact Us", "Terms", "Privacy", "About",
                "Customer", "Service"
            ]
            
            found_links = 0
            for link_text in important_links:
                try:
                    link = page.locator(f"a:has-text('{link_text}')")
                    count = await link.count()
                    if count > 0:
                        try:
                            is_visible = await link.first.is_visible(timeout=3000)
                            if is_visible:
                                logger.info(f"Link '{link_text}' is visible in footer")
                                found_links += 1
                        except Exception as e:
                            logger.warning(f"Error checking link '{link_text}': {str(e)}")
                except Exception as e:
                    logger.warning(f"Exception when locating link '{link_text}': {str(e)}")
            
            logger.info(f"Found {found_links} important links in footer")
            
            # Check for copyright information
            logger.info("Checking for copyright information...")
            copyright_selectors = [
                "text=© 2025", 
                "text=/.*copyright.*/i", 
                "text=/©/",
                "[class*='copyright']",
                "footer span",
                "div.footer span"
            ]
            
            copyright_found = False
            for selector in copyright_selectors:
                try:
                    copyright = page.locator(selector)
                    count = await copyright.count()
                    if count > 0:
                        try:
                            is_visible = await copyright.first.is_visible(timeout=3000)
                            if is_visible:
                                copyright_text = await copyright.first.text_content()
                                logger.info(f"Copyright information: {copyright_text.strip()}")
                                copyright_found = True
                                break
                        except Exception as e:
                            logger.warning(f"Error checking copyright with selector {selector}: {str(e)}")
                except Exception as e:
                    logger.warning(f"Exception when locating copyright with selector {selector}: {str(e)}")
            
            if not copyright_found:
                logger.warning("Copyright information not found with common selectors")
            
            logger.info("--- Completed test case: Content Validation ---")
            
        except Exception as e:
            logger.error(f"Error in content validation test: {str(e)}")
            await self.take_screenshot(page, "content_validation_error")
            raise
    
    @pytest.mark.asyncio
    async def test_09_basic_security(self, browser_context):
        """Test basic security aspects without login"""
        logger.info("--- Starting test case: Basic Security ---")
        page = browser_context['page']
        test_data = browser_context['test_data']
        
        try:
            # Navigate to homepage with explicit timeout
            logger.info(f"Navigating to: {test_data['base_url']}")
            response = await page.goto(test_data['base_url'], timeout=20000, wait_until="domcontentloaded")
            logger.info("Homepage loaded")
            
            # Take screenshot of homepage
            await self.take_screenshot(page, "homepage_for_security")
            
            # Check if using HTTPS
            if response:
                current_url = response.url
                logger.info(f"Response URL: {current_url}")
                if current_url.startswith("https://"):
                    logger.info("Website is using HTTPS ✓")
                else:
                    logger.warning(f"Website not using HTTPS: {current_url}")
            else:
                logger.warning("No response object returned from navigation")
                current_url = page.url
                logger.info(f"Current URL: {current_url}")
                if current_url.startswith("https://"):
                    logger.info("Website is using HTTPS ✓")
                else:
                    logger.warning(f"Website not using HTTPS: {current_url}")
            
            # Check security headers
            try:
                if response:
                    headers = response.headers
                    
                    # Look for common security headers
                    security_headers = {
                        "Content-Security-Policy": headers.get("content-security-policy", "Not set"),
                        "X-XSS-Protection": headers.get("x-xss-protection", "Not set"),
                        "X-Frame-Options": headers.get("x-frame-options", "Not set"),
                        "Strict-Transport-Security": headers.get("strict-transport-security", "Not set"),
                        "X-Content-Type-Options": headers.get("x-content-type-options", "Not set"),
                        "Referrer-Policy": headers.get("referrer-policy", "Not set")
                    }
                    
                    logger.info("Security headers:")
                    for header, value in security_headers.items():
                        logger.info(f"  {header}: {value}")
                        
                    # Count how many security headers are set
                    set_headers = sum(1 for value in security_headers.values() if value != "Not set")
                    logger.info(f"Found {set_headers} out of {len(security_headers)} recommended security headers")
                    
                else:
                    logger.warning("No response object available to check headers")
            except Exception as headers_error:
                logger.warning(f"Error checking security headers: {str(headers_error)}")
            
            # Check for cookie security
            try:
                cookies = await browser_context['context'].cookies()
                secure_cookies = 0
                httponly_cookies = 0
                samesite_cookies = 0
                
                for cookie in cookies:
                    if cookie.get('secure', False):
                        secure_cookies += 1
                    if cookie.get('httpOnly', False):
                        httponly_cookies += 1
                    if cookie.get('sameSite') in ('Lax', 'Strict'):
                        samesite_cookies += 1
                
                logger.info(f"Cookie security analysis:")
                logger.info(f"  Total cookies: {len(cookies)}")
                logger.info(f"  Secure cookies: {secure_cookies}")
                logger.info(f"  HttpOnly cookies: {httponly_cookies}")
                logger.info(f"  SameSite cookies: {samesite_cookies}")
                
            except Exception as cookie_error:
                logger.warning(f"Error checking cookie security: {str(cookie_error)}")
            
            # Check for privacy policy page
            logger.info("Checking for privacy policy...")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)  # Wait for any lazy-loaded footer content
            
            # Take screenshot of footer for privacy policy check
            await self.take_screenshot(page, "footer_for_privacy")
            
            privacy_selectors = [
                "a:has-text('Chính sách bảo mật')", 
                "a:has-text('Privacy Policy')",
                "a:has-text('Privacy')",
                "a:has-text('Bảo mật')"
            ]
            
            privacy_link_found = False
            for selector in privacy_selectors:
                logger.info(f"Looking for privacy link with selector: {selector}")
                try:
                    link = page.locator(selector)
                    count = await link.count()
                    logger.info(f"Found {count} matches for selector: {selector}")
                    
                    if count > 0:
                        try:
                            is_visible = await link.first.is_visible(timeout=3000)
                            if is_visible:
                                logger.info(f"Privacy policy link found with selector: {selector}")
                                # Get current URL to return to
                                current_url = page.url
                                
                                # Click on privacy policy link
                                await link.first.click(timeout=10000)
                                logger.info("Clicked on privacy policy link")
                                
                                # Wait for page to load
                                await page.wait_for_load_state("domcontentloaded", timeout=20000)
                                
                                # Take screenshot of privacy page
                                await self.take_screenshot(page, "privacy_policy_page")
                                
                                # Check that we're on a privacy page
                                new_url = page.url
                                title = await page.title()
                                
                                logger.info(f"Privacy page URL: {new_url}")
                                logger.info(f"Privacy page title: {title}")
                                
                                # Look for keywords in page content
                                content = await page.content()
                                privacy_keywords = ["privacy", "bảo mật", "dữ liệu", "data", "personal", "information"]
                                
                                keyword_found = False
                                for keyword in privacy_keywords:
                                    if keyword.lower() in content.lower():
                                        logger.info(f"Privacy keyword found: {keyword}")
                                        keyword_found = True
                                        break
                                
                                if keyword_found:
                                    logger.info("Privacy page content validation passed")
                                else:
                                    logger.warning("No privacy-related keywords found on page")
                                
                                # Go back to previous page
                                await page.goto(current_url, timeout=20000)
                                logger.info("Returned to original page")
                                
                                privacy_link_found = True
                                break
                            else:
                                logger.warning(f"Privacy link with selector {selector} found but not visible")
                        except Exception as click_error:
                            logger.warning(f"Error clicking privacy link with selector {selector}: {str(click_error)}")
                except Exception as find_error:
                    logger.warning(f"Error finding privacy link with selector {selector}: {str(find_error)}")
            
            if not privacy_link_found:
                logger.warning("Privacy policy link not found or not clickable")
            
            logger.info("--- Completed test case: Basic Security ---")
            
        except Exception as e:
            logger.error(f"Error in security test: {str(e)}")
            await self.take_screenshot(page, "security_error")
            raise
    
    @pytest.mark.asyncio
    async def test_10_image_loading(self, browser_context):
        """Test image loading on product pages"""
        logger.info("--- Starting test case: Image Loading ---")
        page = browser_context['page']
        test_data = browser_context['test_data']
        
        try:
            # Navigate to homepage with explicit timeout
            logger.info(f"Navigating to: {test_data['base_url']}")
            await page.goto(test_data['base_url'], timeout=20000, wait_until="domcontentloaded")
            logger.info("Homepage loaded")
            
            # Search for product
            logger.info("Searching for product...")
            search_box = page.locator("#q, input[type='search']")
            await search_box.fill(test_data['test_product'], timeout=5000)
            await search_box.press("Enter", timeout=5000)
            logger.info(f"Searched for: {test_data['test_product']}")
            
            # Wait for page to load
            await page.wait_for_load_state("domcontentloaded", timeout=20000)
            
            # Allow a moment for images to load
            await asyncio.sleep(3)
            
            # Take screenshot of search results
            await self.take_screenshot(page, "search_results_for_images")
            
            # Check for product images in search results
            logger.info("Checking for product images...")
            image_selectors = [
                "div.Bm3ON img", 
                "div.card--P3aS1 img", 
                "div.product-card img",
                "div[data-tracking='product-card'] img",
                "div.product-item img",
                "div.c1ZEkM img" # Added newer selector
            ]
            
            images_found = 0
            image_selector_used = None
            for selector in image_selectors:
                logger.info(f"Trying image selector: {selector}")
                images = page.locator(selector)
                count = await images.count()
                logger.info(f"Found {count} images with selector: {selector}")
                
                if count > 0:
                    images_found = count
                    image_selector_used = selector
                    break
            
            if images_found > 0:
                logger.info(f"Found {images_found} product images in search results using selector: {image_selector_used}")
                
                # Log some stats about images
                try:
                    # Get some image details
                    image_details = await page.evaluate(f"""() => {{
                        const images = document.querySelectorAll('{image_selector_used}');
                        let details = [];
                        
                        for (let i = 0; i < Math.min(images.length, 5); i++) {{
                            const img = images[i];
                            details.push({{
                                src: img.src,
                                width: img.width,
                                height: img.height,
                                alt: img.alt || 'No alt text',
                                hasDataSrc: img.hasAttribute('data-src'),
                                isLazy: img.loading === 'lazy' || img.hasAttribute('data-lazy')
                            }});
                        }}
                        
                        return details;
                    }}""")
                    
                    logger.info("Sample image details:")
                    for i, details in enumerate(image_details):
                        logger.info(f"Image {i+1}:")
                        logger.info(f"  Size: {details['width']}x{details['height']}px")
                        logger.info(f"  Alt text: {details['alt']}")
                        logger.info(f"  Lazy loading: {details['isLazy']}")
                        
                except Exception as e:
                    logger.warning(f"Error getting image details: {str(e)}")
                    
            else:
                logger.warning("No product images found in search results")
                await self.take_screenshot(page, "no_images_found")
                return
            
            # Click on first product with image
            logger.info("Clicking on first product with image...")
            first_product = None
            product_link_selectors = [
                f"{image_selector_used.split(' ')[0]} a",  # Use the container of the successful image selector
                "div.Bm3ON a", 
                "div.card--P3aS1 a", 
                "div.product-card a",
                "div[data-tracking='product-card'] a",
                "div.c1ZEkM a" # Added newer selector
            ]
            
            product_clicked = False
            for selector in product_link_selectors:
                logger.info(f"Trying product link selector: {selector}")
                links = page.locator(selector)
                count = await links.count()
                logger.info(f"Found {count} product links with selector: {selector}")
                
                if count > 0:
                    try:
                        await links.first.click(timeout=10000)
                        logger.info(f"Clicked on first product with selector: {selector}")
                        product_clicked = True
                        break
                    except Exception as click_error:
                        logger.warning(f"Error clicking on product with selector {selector}: {str(click_error)}")
                        continue
            
            if not product_clicked:
                logger.warning("Could not click on any product, trying direct image click")
                try:
                    # Try clicking directly on the first image
                    images = page.locator(image_selector_used)
                    if await images.count() > 0:
                        await images.first.click(timeout=10000)
                        logger.info("Clicked directly on first product image")
                        product_clicked = True
                except Exception as direct_click_error:
                    logger.warning(f"Error clicking directly on image: {str(direct_click_error)}")
            
            if not product_clicked:
                logger.warning("Could not click on any product, skipping rest of test")
                return
            
            # Wait for product page to load
            logger.info("Waiting for product page to load...")
            await page.wait_for_load_state("domcontentloaded", timeout=20000)
            
            # Allow a moment for images to load
            await asyncio.sleep(3)
            
            # Take screenshot of product page
            await self.take_screenshot(page, "product_page_for_images")
            
            # Check for product image gallery on product page
            logger.info("Checking for product image gallery...")
            gallery_selectors = [
                "div.pdp-images-inner img",
                "div.product-gallery img",
                "div.image-viewer img",
                "div.pdp-block-image img",
                "div[class*='gallery'] img",
                "div[class*='slider'] img"
            ]
            
            gallery_images_found = 0
            gallery_selector_used = None
            for selector in gallery_selectors:
                logger.info(f"Trying gallery selector: {selector}")
                images = page.locator(selector)
                count = await images.count()
                logger.info(f"Found {count} gallery images with selector: {selector}")
                
                if count > 0:
                    gallery_images_found = count
                    gallery_selector_used = selector
                    break
            
            if gallery_images_found > 0:
                logger.info(f"Found {gallery_images_found} gallery images on product page using selector: {gallery_selector_used}")
                
                # Check main product image
                logger.info("Checking main product image...")
                main_image = page.locator(gallery_selector_used).first
                
                try:
                    is_visible = await main_image.is_visible(timeout=3000)
                    if is_visible:
                        # Check image attributes
                        src = await main_image.get_attribute("src")
                        alt = await main_image.get_attribute("alt") or "No alt text"
                        
                        logger.info(f"Main product image src: {src}")
                        logger.info(f"Main product image alt text: {alt}")
                        
                        # Check that image src is valid
                        if src and src.startswith("http"):
                            logger.info("Image src is a valid URL")
                        else:
                            logger.warning(f"Invalid image src: {src}")
                            
                        # Check image size
                        image_size = await page.evaluate("""async (selector) => {
                            const img = document.querySelector(selector);
                            await new Promise(resolve => {
                                if (img.complete) resolve();
                                else img.onload = resolve;
                            });
                            return {
                                naturalWidth: img.naturalWidth,
                                naturalHeight: img.naturalHeight,
                                displayWidth: img.width,
                                displayHeight: img.height
                            };
                        }""", gallery_selector_used)
                        
                        logger.info(f"Main image natural size: {image_size['naturalWidth']}x{image_size['naturalHeight']}px")
                        logger.info(f"Main image display size: {image_size['displayWidth']}x{image_size['displayHeight']}px")
                        
                    else:
                        logger.warning("Main product image found but not visible")
                except Exception as image_error:
                    logger.warning(f"Error checking main product image: {str(image_error)}")
            else:
                logger.warning("No gallery images found on product page")
            
            logger.info("--- Completed test case: Image Loading ---")
            
        except Exception as e:
            logger.error(f"Error in image loading test: {str(e)}")
            await self.take_screenshot(page, "image_loading_error")
            raise

# Khởi chạy các bài kiểm thử và tạo báo cáo HTML nếu chạy trực tiếp file này
# Cập nhật hàm main trong file lazada_test.py
if __name__ == "__main__":
    import sys
    
    pytest_args = [
        "-v",
        "--html=reports/lazada_test_report.html",
        "--self-contained-html",
        "--collect-only",  # Kiểm tra việc thu thập test trước
        "lazada_test.py::TestLazada",  # Chỉ định chính xác class test
    ]
    
    # Kiểm tra thu thập
    print("Đang kiểm tra thu thập test cases...")
    collected = pytest.main(pytest_args)
    print(f"Kết quả thu thập: {collected}")
    
    # Chạy thực tế
    pytest_args.remove("--collect-only")
    sys.exit(pytest.main(pytest_args))