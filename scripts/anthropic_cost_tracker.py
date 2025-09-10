import os
import time
import requests
import json
from functools import lru_cache
from datetime import datetime, timedelta

class AnthropicCostTracker:
    def __init__(self, api_key=None):
        """
        Initialize the Anthropic Cost Tracker
        
        :param api_key: Optional API key. If not provided, uses ANTHROPIC_API_KEY env var
        """
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("No Anthropic API key provided")
        
        # Rate limiting parameters
        self._last_api_call = 0
        self._min_interval = 10  # seconds between API calls
        
        # Caching 
        self.usage_cache = {}
        self.cost_cache = {}
    
    def _rate_limited_request(self, url, method='GET', **kwargs):
        """
        Make a rate-limited API request
        
        :param url: API endpoint URL
        :param method: HTTP method
        :param kwargs: Additional request parameters
        :return: API response
        """
        current_time = time.time()
        
        # Enforce rate limiting
        if current_time - self._last_api_call < self._min_interval:
            wait_time = self._min_interval - (current_time - self._last_api_call)
            time.sleep(wait_time)
        
        # Prepare headers
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        kwargs['headers'] = {**kwargs.get('headers', {}), **headers}
        
        # Make the request
        if method == 'GET':
            response = requests.get(url, **kwargs)
        elif method == 'POST':
            response = requests.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        # Update last API call time
        self._last_api_call = time.time()
        
        # Raise for HTTP errors
        response.raise_for_status()
        
        return response.json()
    
    def get_usage(self, start_time=None, end_time=None):
        """
        Fetch API usage data with caching
        
        :param start_time: Optional start time for usage data
        :param end_time: Optional end time for usage data
        :return: Usage data dictionary
        """
        # Use current time if not specified
        end_time = end_time or datetime.utcnow()
        start_time = start_time or (end_time - timedelta(days=1))
        
        # Convert to ISO format strings
        start_str = start_time.isoformat()
        end_str = end_time.isoformat()
        
        # Check cache first
        cache_key = (start_str, end_str)
        if cache_key in self.usage_cache:
            cached_data, cache_time = self.usage_cache[cache_key]
            # Use cache if less than 1 minute old
            if time.time() - cache_time < 60:
                return cached_data
        
        # Fetch from API
        url = 'https://api.anthropic.com/v1/usage'
        params = {
            'start_time': start_str,
            'end_time': end_str
        }
        
        usage_data = self._rate_limited_request(url, params=params)
        
        # Cache the result
        self.usage_cache[cache_key] = (usage_data, time.time())
        
        return usage_data
    
    def get_cost(self, start_time=None, end_time=None):
        """
        Fetch API cost data with caching
        
        :param start_time: Optional start time for cost data
        :param end_time: Optional end time for cost data
        :return: Cost data dictionary
        """
        # Use current time if not specified
        end_time = end_time or datetime.utcnow()
        start_time = start_time or (end_time - timedelta(days=1))
        
        # Convert to ISO format strings
        start_str = start_time.isoformat()
        end_str = end_time.isoformat()
        
        # Check cache first
        cache_key = (start_str, end_str)
        if cache_key in self.cost_cache:
            cached_data, cache_time = self.cost_cache[cache_key]
            # Use cache if less than 1 minute old
            if time.time() - cache_time < 60:
                return cached_data
        
        # Fetch from API
        url = 'https://api.anthropic.com/v1/cost'
        params = {
            'start_time': start_str,
            'end_time': end_str
        }
        
        cost_data = self._rate_limited_request(url, params=params)
        
        # Cache the result
        self.cost_cache[cache_key] = (cost_data, time.time())
        
        return cost_data
    
    def get_budget_summary(self):
        """
        Generate a comprehensive budget summary
        
        :return: Dictionary with budget and usage information
        """
        usage = self.get_usage()
        cost = self.get_cost()
        
        return {
            'total_tokens': usage.get('total_tokens', 0),
            'total_cost': cost.get('total_cost', 0),
            'models_used': usage.get('models', []),
            'timestamp': datetime.utcnow().isoformat()
        }

def main():
    """
    Example usage and testing
    """
    try:
        tracker = AnthropicCostTracker()
        summary = tracker.get_budget_summary()
        print(json.dumps(summary, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()