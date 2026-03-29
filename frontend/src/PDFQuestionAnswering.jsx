import React, { useState } from "react";
import { Upload, MessageSquare, FileText, AlertCircle } from "lucide-react";
import { Alert, AlertTitle } from "@mui/material";

const API_URL = import.meta.env.VITE_API_URL;

const PDFQuestionAnswering = () => {
 const [files, setFiles] = useState([]);
 const [isUploading, setIsUploading] = useState(false);
 const [uploadStatus, setUploadStatus] = useState(null);
 const [question, setQuestion] = useState("");
 const [answer, setAnswer] = useState(null);
 const [isLoading, setIsLoading] = useState(false);

 const handleFileUpload = async (e) => {
   const selectedFiles = Array.from(e.target.files);

   if (selectedFiles.length > 5) {
     setUploadStatus({ type: "error", message: "Maximum 5 files allowed" });
     return;
   }

   setIsUploading(true);
   setFiles(selectedFiles);

   const formData = new FormData();
   selectedFiles.forEach((file) => {
     formData.append("files[]", file);
   });

   try {
     const response = await fetch(`${API_URL}/upload-pdfs`, {
       method: "POST",
       body: formData,
       headers: {
         Accept: "application/json", // Allow JSON responses
       },
     });

     if (!response.ok) {
       const errorData = await response.json();
       throw new Error(errorData.error || "Upload failed");
     }

     const data = await response.json();
     setUploadStatus({
       type: "success",
       message: `${data.message} (${data.document_chunks} chunks created)`,
     });
   } catch (error) {
     setUploadStatus({ type: "error", message: error.message });
   } finally {
     setIsUploading(false);
   }
 };

 const handleQuestionSubmit = async (e) => {
   e.preventDefault();
   if (!question.trim()) return;

   setIsLoading(true);

   try {
     const response = await fetch(`${API_URL}/ask-question`, {
       method: "POST",
       headers: {
         "Content-Type": "application/json",
       },
       body: JSON.stringify({ text: question }),
     });

     if (!response.ok) {
       const errorData = await response.json();
       throw new Error(errorData.error || "Failed to get answer");
     }

     const data = await response.json();
     setAnswer(data);
   } catch (error) {
     setUploadStatus({ type: "error", message: error.message });
   } finally {
     setIsLoading(false);
   }
 };

 return (
   <div>
     <div>
       <h1>PDF Question Answering System</h1>

       {/* File Upload Section */}
       <div>
         <div>
           <Upload />
         </div>
         <div>
           <label>
             Choose PDFs
             <input
               type="file"
               multiple
               accept=".pdf"
               onChange={handleFileUpload}
             />
           </label>
         </div>
         <p>Upload up to 5 PDF files</p>

         {files.length > 0 && (
           <div>
             <h3>Uploaded Files:</h3>
             <ul
               style={{
                 display: "flex",
                 justifyContent: "center",
                 alignItems: "center",
                 gap: "40px",
               }}
             >
               {files.map((file, index) => (
                 <li key={index}>
                   <FileText />
                   {file.name}
                 </li>
               ))}
             </ul>
           </div>
         )}
       </div>

       {/* Status Messages */}
       {uploadStatus && (
         <Alert
           severity={uploadStatus.type === "error" ? "error" : "info"}
           sx={{
             display: "flex",
             justifyContent: "center",
             alignItems: "center",
           }}
         >
           <AlertTitle>
             {uploadStatus.type === "error" ? "Error" : "Info"}
           </AlertTitle>
           {uploadStatus.message}
         </Alert>
       )}

       {/* Question Input */}
       <form onSubmit={handleQuestionSubmit}>
         <div>
           <input
             type="text"
             value={question}
             onChange={(e) => setQuestion(e.target.value)}
             placeholder="Ask a question about your PDFs..."
             disabled={isUploading || files.length === 0}
             style={{ width: "500px" }}
           />
           <button
             type="submit"
             disabled={isLoading || isUploading || files.length === 0}
           >
             {isLoading ? "Thinking..." : "Ask"}
           </button>
         </div>
       </form>

       {/* Answer Display */}
       {answer && (
         <div>
           <div>
             <h3>
               <MessageSquare />
               Answer
             </h3>
             <p>{answer.answer}</p>
           </div>

           <div>
             <h4>Sources:</h4>
             <ul>
               {answer.sources.map((source, index) => (
                 <li key={index}>{source}</li>
               ))}
             </ul>
           </div>
         </div>
       )}

       {/* Loading State */}
       {isLoading && (
         <div>
           <div>Processing your question...</div>
         </div>
       )}
     </div>
   </div>
 );
};

export default PDFQuestionAnswering;