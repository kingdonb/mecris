import { useAuth } from 'react-oidc-context'
import Dashboard from './Dashboard'
import './App.css'

function App() {
  const auth = useAuth();

  if (auth.isLoading) {
    return <div className="loading-screen">INITIATING NEURAL LINK...</div>;
  }

  if (auth.error) {
    return <div className="error-screen">LINK FAILURE: {auth.error.message}</div>;
  }

  if (auth.isAuthenticated) {
    return <Dashboard userToken={auth.user?.access_token} />;
  }

  return (
    <div className="login-screen">
      <div className="login-container">
        <h1>MECRIS</h1>
        <p>PERSISTENT COGNITIVE AGENT SYSTEM</p>
        <button onClick={() => auth.signinRedirect()} className="login-btn">
          CONNECT TO NEURAL LINK
        </button>
      </div>
    </div>
  );
}

export default App
