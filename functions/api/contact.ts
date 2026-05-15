export const onRequestPost: PagesFunction = async (context) => {
  try {
    const data = await context.request.json();
    
    // In a real scenario, you would send an email here using Mailchannels or another service
    console.log("Received contact form data:", data);

    return new Response(JSON.stringify({ 
      success: true, 
      message: "Message received successfully via Cloudflare Worker!" 
    }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(JSON.stringify({ 
      success: false, 
      message: "Failed to process request" 
    }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }
};
