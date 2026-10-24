"""Run after starting the local Flask server; screenshots contain no credentials."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH','/private/tmp/reboot-browser')
root=Path(__file__).resolve().parents[1]
BASE_URL=os.getenv('REBOOT_TEST_URL','http://127.0.0.1:5050').rstrip('/')
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    assert page.goto(BASE_URL+'/').status==200
    page.wait_for_load_state('networkidle')
    page.screenshot(path=str(root/'artifacts/home-desktop.png'),full_page=True)
    before=page.locator('.bottle-scroll').evaluate('(el)=>getComputedStyle(el).transform')
    page.evaluate('window.scrollTo(0,500)')
    page.wait_for_timeout(700)
    after=page.locator('.bottle-scroll').evaluate('(el)=>getComputedStyle(el).transform')
    assert before!=after,'Scroll must change the independent bottle wrapper transform'
    page.goto(BASE_URL+'/')
    for expected in ['original_lemon','original_cherry','balance_lime','balance_lemon','balance_cherry','gummy_original','gummy_balance','original_lime']:
        page.locator('#shot-button').click()
        page.locator('[data-showcase][aria-busy="true"]').wait_for(state='detached')
        assert page.locator('[data-showcase]').get_attribute('data-product')==expected
    page.get_by_role('tab',name='BALANCE',exact=True).click()
    page.locator('[data-flavor="cherry"] .drink-select').click()
    assert page.locator('#drink-name').inner_text()=='BALANCE CHERRY'
    page.locator('[data-gummy="balance"]').click()
    assert page.locator('#gummy-name').inner_text()=='BALANCE GUMMY'
    page.goto(BASE_URL+'/products/')
    page.get_by_role('button',name='Drinks',exact=True).click()
    assert page.locator('[data-product-line]:visible').count()==2
    page.goto(BASE_URL+'/products/drink-balance')
    page.get_by_role('button',name='Cherry',exact=True).click()
    assert 'cherry' in page.locator('.detail-shot').get_attribute('src')
    page.screenshot(path=str(root/'artifacts/product-desktop.png'),full_page=True)
    page.goto(BASE_URL+'/auth/login')
    page.screenshot(path=str(root/'artifacts/login-desktop.png'),full_page=True)
    page.goto(BASE_URL+'/vibe-test/')
    page.get_by_role('button',name='Find my vibe').click()
    for _ in range(3): page.locator('.quiz-options button').first.click()
    assert page.get_by_role('link',name='Meet your Reboot').get_attribute('href')=='/products/jelly-original'
    page.set_viewport_size({'width':390,'height':844})
    for path in ['/','/products/','/products/jelly-balance','/auth/login','/vibe-test/','/about/story','/contact/']:
        page.goto(BASE_URL+path)
        page.wait_for_load_state('networkidle')
        width=page.evaluate('document.documentElement.scrollWidth')
        assert width<=390,f'Horizontal overflow on {path}: {width}'
        if path=='/': page.screenshot(path=str(root/'artifacts/home-mobile.png'),full_page=True)
    page.get_by_role('button',name='Menu').click()
    assert page.locator('#navigation').is_visible()
    page.keyboard.press('Escape')
    assert not page.locator('#navigation').is_visible()
    page.emulate_media(reduced_motion='reduce')
    page.goto(BASE_URL+'/')
    assert page.locator('.marquee>div').evaluate('(el)=>getComputedStyle(el).animationName')=='none'
    assert not errors,errors
    # Read local account credentials without writing them to logs or screenshots.
    from dotenv import dotenv_values
    credentials=dotenv_values(root/'.env')
    for role in ('ADMIN','CUSTOMER'):
        page.goto(BASE_URL+'/auth/login')
        page.get_by_label('Email address').fill(credentials[role+'_EMAIL'])
        page.get_by_label('Password',exact=True).fill(credentials[role+'_PASSWORD'])
        page.locator('.auth-form form button[type=submit], .auth-form form button.btn.primary').click()
        page.wait_for_load_state('networkidle')
        assert '/admin/' in page.url if role=='ADMIN' else page.url.endswith('/')
        assert page.evaluate('document.documentElement.scrollWidth')<=390
        if role=='ADMIN':
            page.set_viewport_size({'width':1440,'height':1000})
            page.screenshot(path=str(root/'artifacts/admin-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
        page.goto(BASE_URL+'/auth/logout')
        page.get_by_role('button',name='Sign out',exact=False).click()
        assert page.get_by_role('link',name='Sign in again').is_visible()
    assert not errors,errors
    browser.close()
print('Browser checks passed: desktop/mobile, scroll motion, filters, flavor preview, quiz, menu, reduced motion; no JS errors.')
