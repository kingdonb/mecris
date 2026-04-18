import ReactDOM from 'react-dom/client'
import { AuthProvider } from 'react-oidc-context'
import { WebStorageStateStore } from 'oidc-client-ts'
import App from './App'
import './index.css'

const oidcConfig = {
  authority: "https://metnoom.urmanac.com",
  client_id: "21f65a91-c4df-468d-a256-3b66a54c6d5f",
  // Ensure this EXACTLY matches what you saved in Pocket-ID (check the trailing slash!)
  redirect_uri: "http://localhost:5173/", 
  userStore: new WebStorageStateStore({ store: window.localStorage }),
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname);
  }
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <AuthProvider {...oidcConfig}>
    <App />
  </AuthProvider>
)
