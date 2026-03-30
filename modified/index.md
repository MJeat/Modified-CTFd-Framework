# Note that this is for changing the landing page. 

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/559e3fa2-11cf-4e4b-8048-12249423c1c8" />

## Original Code:

```
<div class="row">
    <div class="col-md-6 offset-md-3">
        <img class="w-100 mx-auto d-block" style="max-width: 500px;padding: 50px;padding-top: 14vh;" src="/themes/core/static/img/logo.png?d=d2021974" />
        <h3 class="text-center">
            <p>A cool CTF platform from <a href="https://ctfd.io">ctfd.io</a></p>
            <p>Follow us on social media:</p>
            <a href="https://twitter.com/ctfdio"><i class="fab fa-twitter fa-2x" aria-hidden="true"></i></a>&nbsp;
            <a href="https://facebook.com/ctfdio"><i class="fab fa-facebook fa-2x" aria-hidden="true"></i></a>&nbsp;
            <a href="https://github.com/ctfd"><i class="fab fa-github fa-2x" aria-hidden="true"></i></a>
        </h3>
        <br>
        <h4 class="text-center">
            <a href="admin">Click here</a> to login and setup your CTF
        </h4>
    </div>
</div>
```

# Modified Code: 

To change this, you need to go to Admin Panel > Pages > All Pages > Index

```
<style>
  :root {
    --cyan: #00f5ff;
    --magenta: #ff006e;
  }

  .hero-section {
    padding: 6rem 0;
    text-align: center;
    position: relative;
    background: rgba(10, 5, 15, 0.4);
    border: 1px solid rgba(0, 245, 255, 0.1);
    border-radius: 15px;
    margin-top: 3rem;
  }

  /* Decorative Cyan/Magenta Corners */
  .hero-section::before {
    content: ""; position: absolute; top: -2px; left: -2px; width: 40px; height: 40px;
    border-top: 3px solid var(--cyan); border-left: 3px solid var(--cyan);
  }
  .hero-section::after {
    content: ""; position: absolute; bottom: -2px; right: -2px; width: 40px; height: 40px;
    border-bottom: 3px solid var(--magenta); border-right: 3px solid var(--magenta);
  }

  .glitch-title {
    color: var(--cyan);
    font-weight: 900;
    font-size: 3.5rem;
    letter-spacing: 8px;
    text-transform: uppercase;
    text-shadow: 0 0 20px rgba(0, 245, 255, 0.4);
    margin-bottom: 1rem;
  }

  .sub-title {
    color: var(--magenta);
    font-family: monospace;
    font-size: 1.2rem;
    letter-spacing: 3px;
    margin-bottom: 3rem;
  }

  .feature-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 2rem;
    border-radius: 10px;
    transition: all 0.3s ease;
    height: 100%;
  }

  .feature-card:hover {
    border-color: var(--cyan);
    transform: translateY(-5px);
    background: rgba(0, 245, 255, 0.05);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  }

  .btn-cyber-outline {
    border: 1px solid var(--cyan);
    color: var(--cyan);
    text-transform: uppercase;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 10px 25px;
    transition: 0.3s;
  }

  .btn-cyber-outline:hover {
    background: var(--cyan);
    color: #000;
    box-shadow: 0 0 20px var(--cyan);
  }

  .social-icon {
    color: #fff;
    font-size: 1.5rem;
    margin: 0 15px;
    transition: 0.3s;
  }

  .social-icon:hover {
    color: var(--magenta);
    text-shadow: 0 0 10px var(--magenta);
  }
</style>

<div class="container">
  <div class="hero-section mb-5">
    <h1 class="glitch-title">AUPP CTF CLUB</h1>
    <p class="sub-title">&gt; INITIALIZING SECURE TRAINING ENVIRONMENT_</p>
    
    <div class="mt-4">
      <a href="/register" class="btn btn-cyber-outline mx-2">Join Recruitment</a>
      <a href="/login" class="btn btn-cyber-outline mx-2" style="border-color: var(--magenta); color: var(--magenta);">Access Portal</a>
    </div>
  </div>

  <div class="row text-center mt-5">
    <div class="col-md-4 mb-4">
      <div class="feature-card">
        <i class="fas fa-user-secret fa-3x mb-3" style="color: var(--cyan);"></i>
        <h4 style="color: #fff;">Training Ground</h4>
        <p class="text-muted">Year-round access to labs and challenges for all skill levels.</p>
      </div>
    </div>

    <div class="col-md-4 mb-4">
      <div class="feature-card">
        <i class="fab fa-facebook fa-3x mb-3" style="color: var(--magenta);"></i>
        <h4 style="color: #fff;">Facebook Community</h4>
        <p class="text-muted">Stay updated with club news and connect with other students.</p>
        <a href="https://www.facebook.com/profile.php?id=61586986919120" target="_blank" class="btn btn-link" style="color: var(--cyan); text-decoration: none;">Visit Page &rarr;</a>
      </div>
    </div>

    <div class="col-md-4 mb-4">
      <div class="feature-card">
        <i class="fas fa-trophy fa-3x mb-3" style="color: var(--cyan);"></i>
        <h4 style="color: #fff;">Competitions</h4>
        <p class="text-muted">Compete in upcoming seasonal CTFs and win rewards.</p>
      </div>
    </div>
  </div>

  <div class="text-center py-5">
    <hr style="border-color: rgba(255,255,255,0.1); width: 50%; margin: auto; margin-bottom: 30px;">
    <a href="https://www.facebook.com/profile.php?id=61586986919120" class="social-icon"><i class="fab fa-facebook"></i></a>
    <a href="#"><i class="fab fa-github social-icon"></i></a>
    <a href="#"><i class="fab fa-discord social-icon"></i></a>
  </div>
</div>
```


# Result:

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/44217443-fc6d-49c7-94b1-b5ca713cd325" />

