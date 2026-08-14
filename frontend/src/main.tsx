import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
// Loaded first so component CSS modules override the shared utility classes
// (.skeleton-line and friends) when both sit on the same element.
import './app.css';
import App from './App';

createRoot(document.getElementById('app') as HTMLElement).render(
	<BrowserRouter>
		<App />
	</BrowserRouter>
);
