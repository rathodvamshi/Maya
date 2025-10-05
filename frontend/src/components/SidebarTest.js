import React from 'react';
import LeftSidebarNew from './LeftSidebarNew';

/*
 * Temporary SidebarTest component.
 * This satisfies the existing import and route in App.js ("/sidebar-test").
 * Replace or expand as needed, or remove the route/import if no longer required.
 */
export default function SidebarTest() {
  return (
    <div style={{ display: 'flex', height: '100%', minHeight: '80vh' }}>
      <LeftSidebarNew />
      <div style={{ padding: '2rem', flex: 1 }}>
        <h2>Sidebar Test Page</h2>
        <p>This is a placeholder page for validating the new sidebar layout.</p>
        <ul>
          <li>Modify <code>src/components/SidebarTest.js</code> to customize.</li>
          <li>Or remove the import and route in <code>App.js</code> if not needed.</li>
        </ul>
      </div>
    </div>
  );
}
