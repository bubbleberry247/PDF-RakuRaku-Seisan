const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.connectOverCDP('http://localhost:9222');
  const contexts = browser.contexts();
  
  for (const context of contexts) {
    const pages = context.pages();
    for (const page of pages) {
      if (page.url().includes('eco-serv')) {
        console.log('Found ETC page:', page.url());
        
        // Get all inputs
        const inputs = await page.$$eval('input', els => 
          els.map((el, i) => ({
            index: i,
            type: el.type,
            id: el.id,
            name: el.name,
            className: el.className,
            placeholder: el.placeholder
          }))
        );
        console.log('\n=== INPUTS ===');
        inputs.forEach(inp => console.log(JSON.stringify(inp)));
        
        // Get all buttons
        const buttons = await page.$$eval('button', els => 
          els.map((el, i) => ({
            index: i,
            type: el.type,
            id: el.id,
            className: el.className,
            text: el.textContent.trim()
          }))
        );
        console.log('\n=== BUTTONS ===');
        buttons.forEach(btn => console.log(JSON.stringify(btn)));
        
        break;
      }
    }
  }
  
  await browser.close();
})();
